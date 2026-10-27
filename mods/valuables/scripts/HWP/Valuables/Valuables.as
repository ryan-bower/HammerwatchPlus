// Valuables (Item::Valuable: vases, chalices, gems, wolf fur, scarab scales)
// turn straight into gold when picked up: PlayerRecord's pickup gives
// GetPrice() gold (PlayerRecord.as, the Item::Valuable branch). Each one's
// m_price is set to its vanilla price times one more than the run's NG+ level
// (g_ngp, set from the save on every level, HWR2GameMode.as): vanilla at NG+0,
// 2x at NG+1, 3x at NG+2. The pickup text follows. The vanilla price is kept, so
// applying it again never compounds. Every machine applies it from its own
// g_ngp (the host's, which every machine's level carries), since each picker's
// own record pays out.
namespace HWP
{
	namespace Valuables
	{
		// tweak/items/items_valuables.sval; Item::Valuable has no list of its own
		array<string> IDS = {
			"scale_green", "wolf_fur", "chalice_bronze", "ceramic_vase", "copper_tankard",
			"brass_statuette", "fine_painting", "silver_goblet", "chalice_silver", "silver_mirror",
			"silver_plate", "ivory_figurine", "crystal_pitcher", "silk_handkerchief", "chalice_gold",
			"gold_statuette", "embroidered_tapestry", "jade_game_board", "jewelry_box", "gold_music_box",
			"masterpiece_painting", "adamant_statuette", "emerald", "sapphire", "ruby", "diamond" };

		dictionary g_base;   // id -> vanilla price
		int g_mult = 1;
		int g_count = 0;

		int Ngp() { return max(0, int(g_ngp + 0.5f)); }

		void Apply()
		{
			g_mult = 1 + Ngp();
			g_count = 0;
			for (uint i = 0; i < IDS.length(); i++)
			{
				auto v = Item::Valuable::Get(HashString(IDS[i]));
				if (v is null)
				{
					HWP::LogError("valuables", "missing valuable " + IDS[i]);
					continue;
				}
				int base;
				if (!g_base.get(IDS[i], base))
				{
					base = v.m_price;
					g_base.set(IDS[i], base);
				}
				v.m_price = base * g_mult;
				v.m_pickupTxt = v.m_name + " " + Resources::GetString(".hud.pickup.gold", {{ "amount", v.m_price }});
				g_count++;
			}
		}

		void CmdValuables(array<string>@ args)
		{
			// drop <id>: a valuable at your feet (host, in a run), for testing
			if (args.length() >= 1 && args[0] == "drop")
			{
				auto rec = GetLocalPlayerRecord();
				if (!Network::IsServer() || g_inTown || rec is null || rec.actor is null)
					return;
				string id = args.length() >= 2 ? args[1] : "ceramic_vase";
				auto d = Item::Valuable::Get(HashString(id));
				if (d is null)
				{
					HWP::LogError("valuables", "missing valuable " + id);
					return;
				}
				Item::DropItem(d, rec.actor.m_unit.GetPosition() + vec3(30, 0, 0), 1, false, null);
				HWP::Log("valuables", "dropped " + id + " worth " + d.m_price);
				return;
			}
			string example = "-";
			auto v = Item::Valuable::Get(HashString("ceramic_vase"));
			int base;
			if (v !is null && g_base.get("ceramic_vase", base))
				example = v.m_name + " " + base + " -> " + v.m_price;
			HWP::Commands::Reply(Resources::GetString(".hwp.valuables.status", {
				{ "mult", "" + g_mult }, { "ngp", Ngp() }, { "count", g_count }, { "example", example } }));
		}
	}
}

namespace Modules
{
	class HWPValuablesModule : Module, HWP::ModuleStart
	{
		HWPValuablesModule()
		{
			super("hwp-valuables");
			HWP::Commands::Register("valuables", " valuables' gold multiplier (1 + NG+); 'drop <id>' drops one (host)", HWP::Commands::Handler(HWP::Valuables::CmdValuables));
			HWP::Valuables::Apply();
			HWP::Log("valuables", "self-check done: " + HWP::Valuables::g_count + " valuables at " + HWP::Valuables::g_mult + "x");
		}

		void Start(StartMode sMode)
		{
			HWP::Valuables::Apply();
		}

		void UpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused) override
		{
			// the mission window's NG+ arrows change g_ngp in town
			if (1 + HWP::Valuables::Ngp() != HWP::Valuables::g_mult)
				HWP::Valuables::Apply();
		}
	}
}
