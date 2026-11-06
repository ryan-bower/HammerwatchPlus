// Salvage (issue #66): the vanilla Destroy of a piece of gear becomes Salvage. The item
// still goes, and it leaves materials, more the higher its level. That covers the bag
// (the character tab) and the town stash's worn, bag and stashed items, through
// hwplib's ItemActions::DestroyHandler.
// The materials are the Enchanter's (EquipmentEnchantShopContent: Crystals upgrade Common
// gear, Dust everything above), on the scale of the vanilla trinket conversion at a
// mission's end (MissionEndMenu: a Common trinket 1 Crystal, Uncommon 3, Rare 1 Dust,
// Epic 3): Common gear 1 Crystal, Uncommon 3, Rare 1 Dust, Epic 3, Legendary and Unique
// 5, times 1 + item level / 10 (upgrades count), times the host's salvage.yield %,
// rounded (at least 1). A Rare item of level 20 gives 3 Dust, a quarter of what the Enchanter asks
// to raise its quality.
// In a run the materials are carried like any picked up ones (banked at the mission's
// end, part of them lost on a failed one); in town they go straight to the town
// (PlayerRecord.GiveMaterial). No gain modifiers: the yield is what the confirm says.
// Settings: salvage.enabled (host; off is the vanilla Destroy), salvage.yield (host).
namespace HWP
{
	namespace Salvage
	{
		bool Enabled() { return HWP::Settings::GetBool("salvage.enabled", true); }

		class Yield
		{
			MaterialType m_type = MaterialType::Crystals;
			int m_amount = 0;

			string Text()
			{
				if (m_type == MaterialType::Dust)
					return Resources::GetString(".hwp.salvage.dust", { { "n", "" + m_amount } });
				if (m_amount == 1)
					return Resources::GetString(".hwp.salvage.crystal");
				return Resources::GetString(".hwp.salvage.crystals", { { "n", "" + m_amount } });
			}
		}

		// what the item salvages into (amount 0: not gear, nothing)
		Yield@ For(Item::Item@ item)
		{
			Yield y;
			auto eq = cast<Equipment::Equipment>(item);
			if (eq is null)
				return y;
			int base = 0;
			auto q = eq.GetQuality();
			if (q == Item::Quality::Common)
				base = 1;
			else if (q == Item::Quality::Uncommon)
				base = 3;
			else if (q == Item::Quality::Rare)
				base = 1;
			else if (q == Item::Quality::Epic)
				base = 3;
			else if (q == Item::Quality::Legendary || q == Item::Quality::Unique)
				base = 5;
			if (q != Item::Quality::Common && q != Item::Quality::Uncommon)
				y.m_type = MaterialType::Dust;
			// legendaries carry a placeholder level below 0 (Equipment.Finalize)
			int level = max(1, eq.GetItemLevel(false));
			float amount = base * (1.0f + level / 10.0f) * HWP::Settings::GetInt("salvage.yield", 100) / 100.0f;
			y.m_amount = amount <= 0 ? 0 : max(1, int(amount + 0.5f));
			return y;
		}

		void Float(PlayerRecord@ record, const string &in text)
		{
			if (record is null || record.actor is null)
				return;
			AddFloatingText(FloatingTextType::Pickup, text, record.actor.m_unit.GetPosition() + vec3(0, -24, 0));
		}

		int g_salvaged = 0;

		class Handler : HWP::ItemActions::DestroyHandler
		{
			string Label(Item::Item@ item) override
			{
				return Enabled() && For(item).m_amount > 0 ? Resources::GetString(".hwp.salvage.label") : "";
			}

			string Confirm(Item::Item@ item) override
			{
				if (!Enabled())
					return "";
				auto y = For(item);
				if (y.m_amount <= 0)
					return "";
				// once per dialog: the confirm's yield in the log (tests read it there)
				HWP::Log("salvage", "confirm: " + item.GetName() + " into " + y.Text());
				return Resources::GetString(".hwp.salvage.confirm", {
					{ "name", "\\c" + Item::QualityColorString(item.GetQuality()) + item.GetName() + "\\d" },
					{ "yield", y.Text() } });
			}

			void Destroyed(PlayerRecord@ record, Item::Item@ item) override
			{
				if (!Enabled())
					return;
				auto y = For(item);
				if (y.m_amount <= 0)
					return;
				int given = record.GiveMaterial(y.m_type, y.m_amount, true);
				g_salvaged++;
				bool town = cast<TownGameMode>(g_gameMode) !is null;
				HWP::Log("salvage", "salvaged " + item.GetName() + " (" + Item::QualityToString(item.GetQuality())
					+ ", ilvl " + cast<Equipment::Equipment>(item).GetItemLevel(false) + ") into " + y.Text()
					+ (town ? " (town)" : " (carried)") + ", given " + given);
				Float(record, Resources::GetString(".hwp.salvage.gained", { { "yield", y.Text() } }));
			}
		}

		// hwp salvage: what each bag item would salvage into, and the materials now
		void CmdSalvage(array<string>@ args)
		{
			auto record = GetLocalPlayerRecord();
			if (record is null)
				return;
			string ret = "salvage: " + (Enabled() ? "on" : "off") + " yield " + HWP::Settings::GetInt("salvage.yield", 100)
				+ "% salvaged " + g_salvaged + "; crystals " + record.GetMaterial(MaterialType::Crystals)
				+ " dust " + record.GetMaterial(MaterialType::Dust) + "; bag";
			for (uint i = 0; i < record.equipInventory.m_items.length(); i++)
			{
				auto item = record.equipInventory.m_items[i];
				if (item is null)
					continue;
				ret += "; " + i + " " + item.GetName() + " " + Item::QualityToString(item.GetQuality()) + " ilvl "
					+ item.GetItemLevel(false) + " -> " + For(item).Text();
			}
			HWP::Commands::Reply(ret);
		}
	}
}

namespace Modules
{
	class HWPSalvageModule : Module
	{
		HWPSalvageModule()
		{
			super("hwp-salvage");
			HWP::ItemActions::SetDestroyHandler(HWP::Salvage::Handler());
			HWP::Commands::Register("salvage", " what each bag item salvages into, and your Crystals and Dust", HWP::Commands::Handler(HWP::Salvage::CmdSalvage));
		}
	}
}
