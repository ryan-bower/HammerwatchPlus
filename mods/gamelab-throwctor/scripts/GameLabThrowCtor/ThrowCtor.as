// throw-ctor probe (gamelab/scenarios/throw-ctor.json): a module constructor that throws.
// Modules::MakeModules makes every direct Module subclass with InstantiateClass, in one loop
// with no try (Modules/Module.as): does one throwing constructor stop the modules after it,
// or the level?
namespace GameLabThrowCtor
{
	class Holder { int x; }
	Holder@ g_null;
	int g_ticks = 0;

	class GameLabThrowCtorModule : Modules::Module
	{
		GameLabThrowCtorModule()
		{
			super("gamelab-throwctor");
			print("[GL-ctor] constructor runs");
			g_null.x++;
		}

		void UpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused) override
		{
			if (++g_ticks % 120 == 0)
				print("[GL-ctor] the module that threw is ticking: " + g_ticks);
		}
	}

	[Hook]
	void GameModeUpdate(BaseGameMode@ gm, int ms, GameInput& gameInput, MenuInput& menuInput)
	{
		auto agm = cast<AGameplayGameMode>(gm);
		if (agm is null || ++g_hookTicks != 240)
			return;
		string ids;
		for (uint i = 0; i < agm.m_modules.length(); i++)
			ids += (i > 0 ? " " : "") + agm.m_modules[i].m_id;
		print("[GL-ctor] " + agm.m_modules.length() + " modules made: " + ids);
	}
	int g_hookTicks = 0;
}
