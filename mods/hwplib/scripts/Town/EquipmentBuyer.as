class EquipmentBuyerShopContent : AShopContent
{
	array<float> m_priceRate;


	EquipmentBuyerShopContent(float priceRate)
	{
		m_priceRate.insertLast(priceRate);
	}

	EquipmentBuyerShopContent(UnitPtr u, SValue& params)
	{
		super(u, params);

		auto rateArr = GetParamArray(u, params, "price-rate", true);
		if (rateArr !is null)
		{
			for (uint i = 0; i < rateArr.length(); i++)
				m_priceRate.insertLast(rateArr[i].GetFloat());
		}
		
		if (m_priceRate.length() <= 0)
			m_priceRate.insertLast(3.0f);
	}

	string GetName() override { return ".npc.shop.equip.sell"; }
	string GetEmptyShopText() override
	{
		if (HWP::Favorites::Enabled() && m_player !is null)
		{
			bool hasFavorites = false;
			for (uint i = 0; i < m_player.equipInventory.m_items.length(); i++)
			{
				auto item = m_player.equipInventory.m_items[i];
				if (item is null)
					continue;
				if (!HWP::Favorites::Protected(item))
					return ".npc.shop.equip.sell.empty";
				hasFavorites = true;
			}
			if (hasFavorites)
				return ".hwp.favorites.empty";
		}
		return ".npc.shop.equip.sell.empty";
	}

	bool Buy(const string &in func, uint hash, IShopItem@ item) override
	{
		if (func != "sell")
			return false;
		auto sale = cast<EquipmentBuyerShopContentItem>(item);
		if (sale is null || m_player is null || sale.m_item is null)
			return false;
		auto eqItem = sale.m_item;
		if (HWP::Favorites::Protected(eqItem))
		{
			GetHUD().AddAnnounce(Resources::GetString(".hwp.favorites.protected"), "ui_error");
			return false;
		}
		// A stale shop row must not pay for an item no longer in the bag.
		if (!m_player.equipInventory.Remove(eqItem))
			return false;
		
		auto cost = item.GetCost();
		if (cost !is null)
			cost.Spend(m_player);
		
		
		print("Sold item " + eqItem.GetName());
		
		return true;
	}

	array<IShopItem@> GetItems() override
	{
		print("EquipmentBuyerShopContent - getitems");
		
		float rate = m_priceRate[min(m_shopLevel, m_priceRate.length() - 1)];
		
		array<IShopItem@> ret;
		for (uint i = 0; i < m_player.equipInventory.m_items.length(); i++)
		{
			auto item = m_player.equipInventory.m_items[i];
			if (item is null)
				continue;
			if (HWP::Favorites::Protected(item))
				continue;
			auto eqItem = cast<Equipment::Equipment>(item);
			if (eqItem is null)
				continue;
			ret.insertLast(EquipmentBuyerShopContentItem(this, eqItem, i, rate));
		}
		return ret;
	}
}

class EquipmentBuyerShopContentItem : IShopItem
{
	EquipmentBuyerShopContent@ m_shop;
	Equipment::Equipment@ m_item;
	uint m_index;
	ShopCost@ m_cost;

	EquipmentBuyerShopContentItem(EquipmentBuyerShopContent@ shop, Equipment::Equipment@ item, uint index, float priceRate)
	{
		@m_shop = shop;
		@m_item = item;
		m_index = index;
		int baseCost = min(50, m_item.GetItemLevel() * 5);
		@m_cost = ShopCost(MaterialType::Gold, -int(m_item.GetPrice() / priceRate + baseCost));
	}

	string GetID() { return m_index; }
	uint GetIDHash() { return m_index; }
	string GetTitle() { return "\\c" + Item::QualityColorString(m_item.GetQuality()) + m_item.GetName(); }
	string GetSubTitle() { return Resources::GetString(".tooltip.equipment.ilvl", {{"ilvl", m_item.GetItemLevelText()}}); }
	string GetDescription() { return ""; }
	ScriptSprite@ GetIcon() { return m_item.GetIcon(); }
	Sprite@ GetBackground() { return GetQualitySprite(m_item.GetQuality()); }
	ShopCost@ GetCost() { return m_cost; }
	bool AutoSpendCost() { return false; }
	string OnFunc() { return "sell"; }
	//bool IsAvailable(PlayerRecord@ player) { return CheckConditionals(m_mission.m_conditionals, player); }
	bool IsAvailable(PlayerRecord@ player)
	{
		return player !is null && !HWP::Favorites::Protected(m_item)
			&& player.equipInventory.m_items.findByRef(m_item) >= 0;
	}
	
	void ShowTooltip(WindowManager@ manager, bool compare)
	{
		auto tt = Item::BuildItemTooltip(m_item, 0, 1, false);
		manager.SetTooltip(tt, true);
	}

	Item::Item@ GetItem() { return m_item; }
}
