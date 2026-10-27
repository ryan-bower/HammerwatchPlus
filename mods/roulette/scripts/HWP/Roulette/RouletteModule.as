// The roulette table's module: the wheel on a tavern table, the host's rounds, and every
// machine's countdown (HWP::Roulette, RouletteTable.as).
//
// The wheel (doodads/hwp/hwp_roulette_wheel.unit) goes on a table in the tavern's main
// hall, since every tavern tier lays its tables out differently: the one nearest ROOM, back
// from the front wall (which hides what stands just behind it), else the one nearest the
// gambler's spot. Only the host produces it (netsynced, core's HWPLocalNPC). Every machine
// sets that table to its bare "default" scene, so the vanilla food and mugs don't sit under
// the wheel. With no table in reach, the wheel stands at the gambler's spot.
namespace HWP
{
	namespace Roulette
	{
		// the gambler's spot (mods/gambler GamblerModule.as): the tavern's gaming corner
		const vec2 CORNER = vec2(-124.0f, -106.0f);
		const int TABLE_RANGE = 160;
		const array<string> TABLES = {
			"doodads/furniture/table_wood_poor_h.unit", "doodads/furniture/table_wood_poor_v.unit",
			"doodads/furniture/table_wood_poor_round.unit", "doodads/furniture/table_wood_poor_square.unit",
			"doodads/furniture/table_wood_common_h.unit", "doodads/furniture/table_wood_common_v.unit",
			"doodads/furniture/table_wood_common_round.unit", "doodads/furniture/table_wood_common_square.unit",
			"doodads/furniture/table_wood_rich_h.unit", "doodads/furniture/table_wood_rich_v.unit",
			"doodads/furniture/table_wood_rich_round.unit", "doodads/furniture/table_wood_rich_square.unit",
			"doodads/furniture/table_wood_rich_big.unit" };
		// the wheel unit sits this far below the table's position, so it draws over the table
		const float WHEEL_DY = 2.0f;

		vec2 g_tablePos;
		string g_tableName;

		// the main hall, away from the front wall (tier 1-2: the round table; tier 3: the long
		// table on the west wall). The feast tables of tier 3's back room lie north of HALL_TOP.
		const vec2 ROOM = vec2(-165.0f, -210.0f);
		const float HALL_TOP = -280.0f;
		const float HALL_BOTTOM = -150.0f;

		// the table nearest from, of those that pass inHall when hallOnly; false when none
		bool Nearest(vec2 from, bool hallOnly, UnitPtr &out table)
		{
			float best = -1.0f;
			for (uint t = 0; t < TABLES.length(); t++)
			{
				auto prod = Resources::GetUnitProducer(TABLES[t]);
				if (prod is null)
					continue;
				auto units = g_scene.FetchUnitsOfType(prod, from, TABLE_RANGE);
				for (uint i = 0; i < units.length(); i++)
				{
					vec2 pos = xy(units[i].GetPosition());
					if (hallOnly && (pos.y < HALL_TOP || pos.y > HALL_BOTTOM))
						continue;
					float d = dist(pos, from);
					if (best < 0.0f || d < best)
					{
						best = d;
						table = units[i];
						g_tableName = TABLES[t];
					}
				}
			}
			return best >= 0.0f;
		}

		bool FindTable(UnitPtr &out table)
		{
			return Nearest(ROOM, true, table) || Nearest(CORNER, false, table);
		}

		bool TavernBuilt()
		{
			return g_currTownRecord !is null && g_currTownRecord.GetVariationOnBuilding(HashString("tavern")) >= 0;
		}
	}
}

namespace Modules
{
	class HWPRouletteModule : Module, HWP::ModuleStart
	{
		int m_delay = 0;
		bool m_placed = false;
		bool m_owedChecked = false;
		// a building upgrade reloads the town and destroys both: the wheel (the host's) and
		// the table it sits on (every machine bares the new one)
		HWP::Town::Kept m_wheel;
		HWP::Town::Kept m_table = HWP::Town::Kept(false);

		HWPRouletteModule()
		{
			super("hwp-roulette");
			HWP::Settings::Sync("roulette.");
			HWP::Roulette::MakeBets();
			HWP::Net::OnEvent("roulette.state", HWP::Net::EventHandler(HWP::Roulette::OnState));
			HWP::Net::OnRequest("roulette.stake", HWP::Net::RequestHandler(HWP::Roulette::OnStake));
			HWP::Net::OnRequest("roulette.hello", HWP::Net::RequestHandler(HWP::Roulette::OnHello));
			HWP::Net::OnRequest("roulette.spin", HWP::Net::RequestHandler(HWP::Roulette::OnSpinNow));
			HWP::Commands::Register("roulette", "the roulette table: [bet <key> <gold> | clear | spin <n>]",
				HWP::Commands::Handler(HWP::Roulette::Cmd));
		}

		void Start(StartMode sMode)
		{
			m_delay = 0;
			m_placed = false;
			m_wheel.Reset();
			m_table.Reset();
			// chips still on the table when the last level ended
			m_owedChecked = HWP::Roulette::RefundOwed();
			if (!g_inTown)
				HWP::Roulette::Close();
		}

		// HWP::Guard (tools/guard_modules.py): a script error here turns this off, not the game
		HWP::Guard m_guardUpdateFrame;
		void UpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused) override
		{
			if (m_guardUpdateFrame.Skip("roulette", "HWPRouletteModule.UpdateFrame"))
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
			if (!m_owedChecked)
				m_owedChecked = HWP::Roulette::RefundOwed();
			if (!g_inTown)
				return;
			HWP::Roulette::Tick(ms);
			// the host runs the rounds while the town has a tavern (built mid-session too)
			if (m_placed && Network::IsServer() && HWP::Roulette::TavernBuilt())
				HWP::Roulette::HostUpdate(ms);

			// let the scene settle before looking for the tables
			if (!m_placed)
			{
				m_delay += ms;
				if (m_delay < 500)
					return;
				m_placed = true;
				if (!HWP::Roulette::TavernBuilt())
				{
					HWP::Log("roulette", "no tavern built yet, no roulette table");
					return;
				}
				Place();
				return;
			}
			// a building upgrade reloads the town without a new Start
			bool wheelGone = m_wheel.Due(ms);
			bool tableGone = m_table.Due(ms);
			if ((wheelGone || tableGone) && HWP::Roulette::TavernBuilt())
			{
				HWP::Log("roulette", "the town was rebuilt, placing the wheel again");
				Place();
			}
		}

		// every machine: the table bare; the host: the wheel on it
		void Place()
		{
			vec2 pos = HWP::Roulette::CORNER;
			UnitPtr table;
			if (HWP::Roulette::FindTable(table))
			{
				pos = xy(table.GetPosition());
				table.SetUnitScene("default", true);
			}
			else
				HWP::Roulette::g_tableName = "";
			m_table.Set(table);
			HWP::Roulette::g_tablePos = pos;
			if (!Network::IsServer())
				return;
			auto prod = Resources::GetUnitProducer(HWP::Roulette::WHEEL_UNIT);
			if (prod is null)
			{
				HWP::LogError("roulette", "missing " + HWP::Roulette::WHEEL_UNIT);
				m_wheel.Set(UnitPtr());
				return;
			}
			// only the table went (the wheel is still up): no second wheel
			UnitPtr old = m_wheel.m_unit;
			if (old.IsValid() && !old.IsDestroyed() && old.GetUnitProducer() is prod)
				old.Destroy();
			UnitPtr wheel = prod.Produce(g_scene, vec3(pos.x, pos.y + HWP::Roulette::WHEEL_DY, 0.0f));
			m_wheel.Set(wheel);
			HWP::Log("roulette", "the wheel is on " + (HWP::Roulette::g_tableName.isEmpty() ? "no table (none in reach)"
				: HWP::Roulette::g_tableName) + " at " + int(pos.x) + "," + int(pos.y)
				+ (wheel.IsValid() ? "" : ": Produce made nothing"));
		}
	}
}
