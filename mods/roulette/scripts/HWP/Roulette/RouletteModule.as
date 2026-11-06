// The roulette table's module: the wheel on a tavern table, the host's rounds, and every
// machine's countdown (HWP::Roulette, RouletteTable.as).
//
// The wheel (doodads/hwp/hwp_roulette_wheel.unit) goes on a table in the tavern's main
// hall, since every tavern tier lays its tables out differently: the one nearest ROOM, back
// from the front wall (which hides what stands just behind it), else the one nearest the
// gambler's spot. Only the host produces it (netsynced, core's HWPLocalNPC). Every machine
// sets that table to its bare "default" scene, so the vanilla food and mugs don't sit under
// the wheel. With no table in reach, the wheel stands at the gambler's spot.
//
// The table is a vanilla Breakable (60 HP, it respawns after ~24 s), and when it broke the
// wheel jumped to another table (issue #63). Every machine now keeps that table's health
// topped up (Shield), so it cannot break. Should it go anyway, the module places the wheel
// again as after a rebuild. A dealer (doodads/hwp/hwp_roulette_dealer.unit, local on every
// machine) stands behind a hall table, toward the nearer of the hall's north and west walls,
// facing it (DealerPos).
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

		bool g_inHall = false; // the wheel's table is a main-hall table (the dealer stands there)

		bool FindTable(UnitPtr &out table)
		{
			g_inHall = Nearest(ROOM, true, table);
			return g_inHall || Nearest(CORNER, false, table);
		}

		// Breakable (Behaviors/Objects/Breakable.as) breaks its unit once m_health runs out,
		// counted on each machine (a hit's NetDamage too). Topped up every frame, no hit
		// gets there; no wood chips fly either. A hit still makes its sound.
		const int TABLE_HP = 1000000000;

		void Shield(UnitPtr table)
		{
			if (!table.IsValid() || table.IsDestroyed())
				return;
			auto brk = cast<Breakable>(table.GetScriptBehavior());
			if (brk is null)
				return;
			brk.m_health = TABLE_HP;
			brk.m_alwaysHitGore = false;
		}

		// the dealer. The hall's inner wall faces (tavern_tier_1..3.pfb, the town's tavern
		// segment at -64,-176; the HWP levels 4-6 reuse tier 3): the north wall's h_32 pieces
		// at y -256 collide down to -240, the west wall's v_32 pieces at x -240 out to -224.
		const string DEALER_UNIT = "doodads/hwp/hwp_roulette_dealer.unit";
		const float WALL_N = -240.0f;
		const float WALL_W = -224.0f;
		const float DEALER_BACK = 20.0f;  // behind the table's centre
		const float DEALER_WALL_N = 4.0f; // at least this far off the north wall
		const float DEALER_WALL_W = 7.0f; // and the west wall (its sprite is wider than its feet)

		// behind the table, toward the nearer wall, facing the table: tiers 1-2 (the round
		// table by the north wall) put him north of it facing south (2), tier 3 (the long
		// table by the west wall) west of it facing east (0), a step back so the table draws
		// over him
		vec2 DealerPos(vec2 table, int &out facing)
		{
			if (table.y - WALL_N <= table.x - WALL_W)
			{
				facing = 2;
				return vec2(table.x, max(WALL_N + DEALER_WALL_N, table.y - DEALER_BACK));
			}
			facing = 0;
			return vec2(max(WALL_W + DEALER_WALL_W, table.x - DEALER_BACK), table.y - 2.0f);
		}

		bool TavernBuilt()
		{
			return g_currTownRecord !is null && g_currTownRecord.GetVariationOnBuilding(HashString("tavern")) >= 0;
		}

		// roulette.enabled (default on). Off: the table shuts (every machine's chips come
		// back), the host takes the wheel away; on again, the module places it again
		bool g_enabled = true;

		void OnSettingChanged(const string &in key)
		{
			if (key.findFirst("roulette.") != 0)
				return;
			bool was = g_enabled;
			g_enabled = HWP::Settings::GetBool("roulette.enabled", true);
			if (was && !g_enabled && g_inTown)
				Close();
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
		HWP::Town::Kept m_dealer = HWP::Town::Kept(false); // every machine's own

		HWPRouletteModule()
		{
			super("hwp-roulette");
			HWP::Settings::Sync("roulette.");
			HWP::Roulette::g_enabled = HWP::Settings::GetBool("roulette.enabled", true);
			HWP::Commands::OnSettingChanged(HWP::Commands::SettingListener(HWP::Roulette::OnSettingChanged));
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
			m_dealer.Reset();
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
			// roulette.enabled off: no wheel (the host takes it away); placed again once back on
			if (!HWP::Roulette::g_enabled)
			{
				UnitPtr wheel = m_wheel.m_unit;
				if (Network::IsServer() && wheel.IsValid() && !wheel.IsDestroyed()
					&& wheel.GetUnitProducer() is Resources::GetUnitProducer(HWP::Roulette::WHEEL_UNIT))
				{
					wheel.Destroy();
					HWP::Log("roulette", "turned off: took the wheel away");
				}
				RemoveDealer();
				m_wheel.Reset();
				m_table.Reset();
				m_dealer.Reset();
				m_placed = false;
				return;
			}
			// the table can't break (a rebuild can hand its id to another unit: same unit file only)
			UnitPtr table = m_table.m_unit;
			if (m_placed && m_table.m_prod !is null && table.IsValid() && !table.IsDestroyed()
				&& table.GetUnitProducer() is m_table.m_prod)
				HWP::Roulette::Shield(table);
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
			bool dealerGone = m_dealer.Due(ms);
			if ((wheelGone || tableGone || dealerGone) && HWP::Roulette::TavernBuilt())
			{
				HWP::Log("roulette", "the " + (tableGone ? "table" : wheelGone ? "wheel" : "dealer")
					+ " went (a rebuild?), placing the wheel again");
				Place();
			}
		}

		void RemoveDealer()
		{
			UnitPtr dealer = m_dealer.m_unit;
			if (dealer.IsValid() && !dealer.IsDestroyed()
				&& dealer.GetUnitProducer() is Resources::GetUnitProducer(HWP::Roulette::DEALER_UNIT))
				dealer.Destroy();
		}

		// every machine: its own dealer behind a hall table
		void PlaceDealer(vec2 tablePos)
		{
			RemoveDealer();
			if (!HWP::Roulette::g_inHall)
			{
				m_dealer.Set(UnitPtr()); // not watched: no dealer away from the hall
				return;
			}
			auto prod = Resources::GetUnitProducer(HWP::Roulette::DEALER_UNIT);
			if (prod is null)
			{
				HWP::LogError("roulette", "missing " + HWP::Roulette::DEALER_UNIT);
				m_dealer.Set(UnitPtr());
				return;
			}
			int facing = 2;
			vec2 at = HWP::Roulette::DealerPos(tablePos, facing);
			UnitPtr dealer = prod.Produce(g_scene, vec3(at.x, at.y, 0.0f));
			if (dealer.IsValid())
				dealer.SetUnitScene("face-" + facing, true);
			m_dealer.Set(dealer);
			HWP::Log("roulette", "the dealer stands at " + int(at.x) + "," + int(at.y) + " facing " + facing
				+ (dealer.IsValid() ? "" : ": Produce made nothing"));
		}

		// every machine: the table bare and unbreakable, the dealer behind it; the host: the
		// wheel on it
		void Place()
		{
			vec2 pos = HWP::Roulette::CORNER;
			UnitPtr table;
			if (HWP::Roulette::FindTable(table))
			{
				pos = xy(table.GetPosition());
				table.SetUnitScene("default", true);
				HWP::Roulette::Shield(table);
			}
			else
				HWP::Roulette::g_tableName = "";
			m_table.Set(table);
			HWP::Roulette::g_tablePos = pos;
			PlaceDealer(pos);
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
