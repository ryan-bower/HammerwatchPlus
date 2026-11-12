namespace GameLabFavorites
{
	int g_failed = 0;
	int g_checked = 0;

	void Check(bool ok, const string &in name)
	{
		g_checked++;
		if (!ok)
			g_failed++;
		HWP::Log("testfavorites", (ok ? "PASS " : "FAIL ") + name);
	}

	void Run(array<string>@ args)
	{
		g_failed = 0;
		g_checked = 0;
		auto local = GetLocalPlayerRecord();
		if (local is null || local.equipped.m_items[0] is null)
		{
			Check(false, "fixture has a main-hand item");
			return;
		}
		bool active = HWP::Favorites::g_active;
		HWP::Favorites::g_active = true;
		auto record = PlayerRecord();
		auto a = cast<Equipment::Equipment>(local.equipped.m_items[0].Copy());
		auto b = cast<Equipment::Equipment>(a.Copy());
		record.equipInventory.Add(a);
		record.equipInventory.Add(b);
		auto action = HWPFavorites::FavoriteAction();
		action.Do(record, a);
		Check(HWP::Favorites::Has(a) && !HWP::Favorites::Has(b), "identical copies are independent");
		Check(action.Label(a) == Resources::GetString(".hwp.favorites.remove"), "favorite action becomes unfavorite");

		auto shop = EquipmentBuyerShopContent(3.0f);
		Check(shop.GetEmptyShopText() == ".npc.shop.equip.sell.empty", "unopened buyer keeps vanilla empty text");
		@shop.m_player = record;
		Check(shop.GetEmptyShopText() == ".npc.shop.equip.sell.empty", "mixed bag keeps vanilla empty text");
		HWP::Favorites::Set(b, true);
		Check(shop.GetEmptyShopText() == ".hwp.favorites.empty" && shop.GetItems().length() == 0,
			"all-favorite bag explains sale protection");
		HWP::Favorites::g_active = false;
		Check(shop.GetEmptyShopText() == ".npc.shop.equip.sell.empty", "disabled favorites keeps vanilla empty text");
		HWP::Favorites::g_active = true;
		HWP::Favorites::Set(b, false);
		auto empty = PlayerRecord();
		@shop.m_player = empty;
		Check(shop.GetEmptyShopText() == ".npc.shop.equip.sell.empty", "empty bag keeps vanilla empty text");
		@shop.m_player = record;
		auto rows = shop.GetItems();
		Check(rows.length() == 1 && rows[0].GetItem() is b, "buyer lists only the unfavorited copy");
		auto stale = EquipmentBuyerShopContentItem(shop, a, 0, 3.0f);
		int gold = record.GetMaterial(MaterialType::Gold);
		Check(!stale.IsAvailable(record), "favorite row unavailable");
		Check(!shop.Buy("sell", 0, stale) && record.equipInventory.m_items.length() == 2
			&& gold == record.GetMaterial(MaterialType::Gold), "direct favorite sale changes neither items nor gold");
		record.equipInventory.Remove(b);
		Check(!shop.Buy("sell", 1, rows[0]) && gold == record.GetMaterial(MaterialType::Gold), "removed row cannot pay again");
		record.equipInventory.Add(b);

		HWP::DataBag bag;
		HWP::Favorites::SavePlayer(record, bag);
		SValueBuilder inv;
		inv.PushArray();
		record.equipInventory.Save(inv);
		inv.PopArray();
		auto saved = inv.Build();
		record.equipInventory.Load(saved.GetArray());
		saved.Delete();
		HWP::Favorites::LoadPlayer(record, bag);
		auto loaded = record.equipInventory.m_items[0];
		Check(HWP::Favorites::Has(loaded) && !HWP::Favorites::Has(record.equipInventory.m_items[1]), "save roundtrip preserves the correct identical copy");
		record.equipInventory.Remove(loaded);
		@record.equipped.m_items[0] = loaded;
		HWP::Favorites::SavePlayer(record, bag);
		HWP::Favorites::Set(loaded, false);
		HWP::Favorites::LoadPlayer(record, bag);
		Check(HWP::Favorites::Has(loaded), "worn favorite roundtrip");

		auto town = TownRecord();
		town.m_townStash.m_tabs[0].Add(loaded);
		HWP::Favorites::SaveTown(town, bag);
		HWP::Favorites::Set(loaded, false);
		HWP::Favorites::LoadTown(town, bag);
		Check(HWP::Favorites::Has(loaded), "stash favorite roundtrip");
		HWP::Favorites::g_active = false;
		Check(!HWP::Favorites::Protected(loaded) && HWP::Favorites::Has(loaded), "off suspends protection without erasing favorites");
		HWP::Favorites::g_active = true;
		record.equipInventory.Add(loaded);
		action.Do(record, loaded);
		Check(!HWP::Favorites::Has(loaded) && shop.GetItems().length() == 2, "unfavorite returns the item to the sale list");
		@record.equipped.m_items[0] = null;

		// Saved slots cannot mark a different item after its contents change.
		HWP::Favorites::Set(loaded, true);
		HWP::Favorites::SavePlayer(record, bag);
		record.equipInventory.Remove(loaded);
		HWP::Favorites::LoadPlayer(record, bag);
		Check(!HWP::Favorites::Has(record.equipInventory.m_items[0]), "missing saved slot does not mark another item");
		if (Equipment::UniqueEquipment::Instances.length() > 0)
		{
			auto def = Equipment::UniqueEquipment::Instances[0];
			record.equipInventory.Clear();
			record.equipInventory.Add(def);
			record.equipInventory.Add(def);
			auto first = record.equipInventory.m_items[0];
			auto second = record.equipInventory.m_items[1];
			HWP::Favorites::Set(first, true);
			Check(first !is second && first !is def && !HWP::Favorites::Has(second), "unique drops have independent identity");
			SValueBuilder ub;
			Item::SaveItem(ub, first);
			auto us = ub.Build();
			auto u1 = Item::LoadItem(us);
			auto u2 = Item::LoadItem(us);
			Check(u1 !is u2 && u1.GetIDHash() == first.GetIDHash(), "unique load creates owned copies with the same id");
			us.Delete();
		}
		else
		{
			Check(false, "unique definitions present");
			Check(false, "unique load prerequisites");
		}
		HWP::Favorites::g_active = active;
		HWP::Log("testfavorites", "finished " + g_checked + " checks, " + g_failed + " failed");
	}
}

namespace Modules
{
	class GameLabFavoritesChecks : Module
	{
		GameLabFavoritesChecks()
		{
			super("gamelab-it-favorites");
			HWP::Commands::Register("testfavorites", " controlled favorite checks (GameLab only)", HWP::Commands::Handler(GameLabFavorites::Run));
		}
	}
}
