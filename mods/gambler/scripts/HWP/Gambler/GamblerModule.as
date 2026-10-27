// Spawns the gambler NPC inside the tavern once the tavern is built. The NPC is
// placed by code instead of editing the tavern prefabs, so no base file is
// overridden. Only the server produces the unit (it is netsynced).
// bet tokens (Tokens.as, per character) in the materials tab's Supplies
// section (core Materials.as); gui/hwp/token.png is a 13x13 chip
class HWPTokenMaterial : HWP::Materials::Material
{
	ScriptSprite@ Icon() override
	{
		return ScriptSprite(Resources::GetTexture2D("gui/hwp/token.png"), vec4(0, 0, 13, 13));
	}

	int Count() override
	{
		return HWP::Gambler::Tokens(GetLocalPlayerRecord());
	}

	string Title() override
	{
		return Resources::GetString(".hwp.gambler.token_title");
	}

	string Text() override
	{
		return Resources::GetString(".hwp.gambler.token_text");
	}
}

namespace Modules
{
	class HWPGamblerModule : Module, HWP::ModuleStart
	{
		bool m_done = false;
		int m_delay = 0;
		HWP::Town::Kept m_kept;   // the gambler unit; a building upgrade destroys it
		bool m_broken = false;    // the unit file is missing: don't retry every second

		HWPGamblerModule()
		{
			super("hwp-gambler");
			HWP::Gambler::InitTokens();
			HWP::Materials::Title("a", ".hwp.gambler.supplies");
			HWP::Materials::Register("a", 0, "hwp-mat-bet-tokens", HWPTokenMaterial());
		}

		// HWP::Guard (tools/guard_modules.py): a script error here turns this off, not the game
		HWP::Guard m_guardUpdateFrame;
		void UpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused) override
		{
			if (m_guardUpdateFrame.Skip("gambler", "HWPGamblerModule.UpdateFrame"))
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
			// a building upgrade (or building the tavern) reloads the town without a new Start
			if (m_done)
			{
				if (!m_broken && m_kept.Due(ms) && g_currTownRecord !is null
					&& g_currTownRecord.GetVariationOnBuilding(HashString("tavern")) >= 0)
					Spawn();
				return;
			}

			// let the scene settle before producing units
			m_delay += ms;
			if (m_delay < 500)
				return;

			if (!g_inTown || !Network::IsServer())
			{
				m_done = true;
				return;
			}
			if (g_currTownRecord is null)
				return;

			m_done = true;
			if (g_currTownRecord.GetVariationOnBuilding(HashString("tavern")) < 0)
			{
				HWP::Log("gambler", "no tavern built yet, no gambler");
				return;
			}
			Spawn();
		}

		void Spawn()
		{
			// tavern segment at (-64, -176) in the town base level, NPC offset (-60, 70)
			vec3 spawnPos = vec3(-124.0f, -106.0f, 0.0f);
			auto prod = Resources::GetUnitProducer("actors/npcs/town/hwp_gambler.unit");
			if (prod is null)
			{
				HWP::LogError("gambler", "missing actors/npcs/town/hwp_gambler.unit");
				m_broken = true;
				return;
			}
			UnitPtr npc = prod.Produce(g_scene, spawnPos);
			m_kept.Set(npc);
			if (!npc.IsValid())
			{
				HWP::LogError("gambler", "Produce returned no unit at (-124, -106)");
				m_broken = true;
				return;
			}
			HWP::Log("gambler", "spawned the gambler in the tavern (unit " + npc.GetId() + " at -124,-106)");
		}

		void Start(StartMode sMode)
		{
			m_done = false;
			m_delay = 0;
			m_kept.Reset();
		}
	}
}
