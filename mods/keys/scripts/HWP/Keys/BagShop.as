// HWP::BagShop: the equipment bag slots for sale (the bag itself is the base library's
// HWP::Bag, BagSlots.as). 1000 g for the first slot, rising to 20000 g for the eighth; the
// exit guard's shop sells them (HWPBagShopItem, GeneralMerchant.as), and so does `hwp bag buy`.
namespace HWP
{
	namespace BagShop
	{
		const array<int> PRICE = { 1000, 2000, 3500, 5500, 8000, 11000, 15000, 20000 };

		// gold for the next slot; 0 when the bag is full size
		int NextPrice(PlayerRecord@ rec)
		{
			int extra = HWP::Bag::Extra(rec);
			return extra >= HWP::Bag::MAX_EXTRA ? 0 : PRICE[extra];
		}

		// the local player buys one slot; false when full size or short of gold
		bool Buy(PlayerRecord@ rec)
		{
			int price = NextPrice(rec);
			if (price <= 0 || rec.GetMaterial(MaterialType::Gold) < price)
				return false;
			rec.GiveMaterial(MaterialType::Gold, -price, true);
			HWP::SaveData::Player(rec).SetInt(HWP::Bag::KEY_EXTRA, HWP::Bag::Extra(rec) + 1);
			HWP::Bag::Apply(rec);
			HWP::Log("keys", rec.GetName() + " bought bag slot " + HWP::Bag::Capacity(rec) + " for " + price + " gold");
			return true;
		}

		void CmdBag(array<string>@ args)
		{
			auto rec = GetLocalPlayerRecord();
			if (rec is null)
				return;
			if (args.length() >= 1 && args[0] == "buy")
			{
				int cost = NextPrice(rec);
				if (!Buy(rec))
				{
					HWP::Commands::Reply(Resources::GetString(cost <= 0 ? ".hwp.bag.status_full" : ".hwp.bag.no_gold", {
						{ "items", int(rec.equipInventory.m_items.length()) }, { "cap", HWP::Bag::Capacity(rec) }, { "price", cost } }));
					return;
				}
			}
			int price = NextPrice(rec);
			HWP::Commands::Reply(Resources::GetString(price > 0 ? ".hwp.bag.status" : ".hwp.bag.status_full", {
				{ "items", int(rec.equipInventory.m_items.length()) }, { "cap", HWP::Bag::Capacity(rec) },
				{ "max", HWP::Bag::BASE + HWP::Bag::MAX_EXTRA }, { "price", price } }));
		}
	}
}
