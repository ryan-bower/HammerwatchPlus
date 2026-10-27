// throw probe (gamelab/scenarios/throw.json): what one mod's runtime exception does to the rest.
// Counted in gameplay frames (GameModeUpdate hook calls):
//   300:        one null access inside try/catch (getExceptionInfo is not registered: throw
//               20261027-030042, "No matching symbol")
//   600..1199:  hook A throws every frame: do hook B, the module and the game go on?
//   1200 on:    the module throws every frame
// A screen shake entry is aged and removed by AGameplayGameMode::UpdateFrame after its module
// loop (AGameplayGameMode.as:335-340), so one added at 400 (quiet), 700 (hook A throwing) and
// 1300 (the module throwing) and read 120 frames later shows whether that code still runs.
namespace GameLabThrow
{
	int g_hookA = 0, g_hookB = 0, g_module = 0;
	ScreenShake@ g_shake;
	string g_shakePhase;

	class Holder { int x; }
	Holder@ g_null;

	void Boom() { g_null.x++; }

	class GameLabThrowModule : Modules::Module
	{
		GameLabThrowModule() { super("gamelab-throw"); }

		void UpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused) override
		{
			if (paused)
				return;
			g_module++;
			if (g_module == 300)
			{
				try { Boom(); }
				catch { print("[GL-throw] caught: a null access (getExceptionInfo is not registered)"); }
			}
			if (g_hookA >= 1200)
				Boom();
		}
	}
}

namespace GameLabThrowA
{
	[Hook]
	void GameModeUpdate(BaseGameMode@ gm, int ms, GameInput& gameInput, MenuInput& menuInput)
	{
		GameLabThrow::g_hookA++;
		if (GameLabThrow::g_hookA >= 600 && GameLabThrow::g_hookA < 1200)
			GameLabThrow::Boom();
	}
}

namespace GameLabThrowB
{
	[Hook]
	void GameModeUpdate(BaseGameMode@ gm, int ms, GameInput& gameInput, MenuInput& menuInput)
	{
		GameLabThrow::g_hookB++;
		int f = GameLabThrow::g_hookB;
		if (f % 120 == 0)
			print("[GL-throw] ticks module " + GameLabThrow::g_module + " hookA " + GameLabThrow::g_hookA + " hookB " + f);
		auto agm = cast<AGameplayGameMode>(gm);
		if (agm is null)
			return;
		if (f == 400 || f == 700 || f == 1300)
		{
			@GameLabThrow::g_shake = ScreenShake();
			GameLabThrow::g_shake.m_time = GameLabThrow::g_shake.m_timeC = 100000;
			GameLabThrow::g_shake.m_amount = 0;
			GameLabThrow::g_shake.m_range = -1;
			agm.m_screenShake.insertLast(GameLabThrow::g_shake);
			GameLabThrow::g_shakePhase = f == 400 ? "quiet" : (f == 700 ? "hookA" : "module");
		}
		if ((f == 520 || f == 820 || f == 1420) && GameLabThrow::g_shake !is null)
			print("[GL-throw] shake " + GameLabThrow::g_shakePhase + ": " + (100000 - GameLabThrow::g_shake.m_timeC) + " ms aged in 120 frames");
	}
}
