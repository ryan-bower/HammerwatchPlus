class EquipmentShopShopContent : AShopContent
{
	array<Equipment::Equipment@> m_eqipmentChoices;

	EquipmentShopShopContent(UnitPtr u, SValue& params)
	{
		super(u, params);
	}

	string GetName() override { return ".npc.shop.equip.buy"; }

	bool Buy(const string &in func, uint hash, IShopItem@ item) override
	{
		if (func != "buy")
			return false;
		
		auto equipmentItem = cast<EquipmentSellerShopContentItem>(item).m_item;
		m_player.GiveItem(equipmentItem);
		
		for (uint i = 0; i < m_eqipmentChoices.length(); i++)
		{
			if (m_eqipmentChoices[i] is equipmentItem)
			{
				m_eqipmentChoices.removeAt(i);
				break;
			}
		}
		
		return true;
	}

	array<IShopItem@> GetItems() override
	{
		if (m_eqipmentChoices.length() <= 0)
		{
			Equipment::Generator gen;
			gen.m_qualities = Item::Quality(int(Item::Quality::Uncommon) | int(Item::Quality::Rare));
			
			int tries = 0;   // HWP firearms: the gun filter below rerolls, never for ever
			while (m_eqipmentChoices.length() < 5 && ++tries <= 200)
			{
				gen.m_ilvl = min(m_player.GetEquipmentDropLevelCap(), max(2, int(g_diffLevel + Modifiers::lerp(vec2(-1, 3), randf()))));
				
				Equipment::Equipment@ bestItem = null;
				int bestItemScore = -1000000;
				for (uint i = 0; i < 5; i++)
				{
					auto newItem = gen.GenerateItem();
					auto req = newItem.GetRequirements();
					
					int goodness = 0;
					if (req.m_str > 0)
						goodness += (m_player.currStats.Str >= req.m_str) ? req.m_str : -req.m_str;
					if (req.m_dex > 0)
						goodness += (m_player.currStats.Dex >= req.m_dex) ? req.m_dex : -req.m_dex;
					if (req.m_int > 0)
						goodness += (m_player.currStats.Int >= req.m_int) ? req.m_int : -req.m_int;
					if (req.m_foc > 0)
						goodness += (m_player.currStats.Foc >= req.m_foc) ? req.m_foc : -req.m_foc;
					if (req.m_vit > 0)
						goodness += (m_player.currStats.Vit >= req.m_vit) ? req.m_vit : -req.m_vit;
					
					if (goodness > bestItemScore)
					{
						@bestItem = newItem;
						bestItemScore = goodness;
					}
				}
				
				auto@ newItem = bestItem;
				
				bool duplicate = false;
				
				auto bItem = cast<Equipment::Item>(newItem);

				if(bItem !is null && !CheckGlobalConditionals(bItem.baseItem.m_conditionals))
				{
					continue;
				}

				// HWP firearms: a Firearms Specialist's weapon offers are guns, nobody else's are (HWP/Firearms/Shops.as)
				if (!HWP::Firearms::ShopKeeps(m_player, newItem))
					continue;

				for (uint i = 0; i < m_eqipmentChoices.length(); i++)
				{
					auto aItem = cast<Equipment::Item>(m_eqipmentChoices[i]);

					if (aItem !is null && bItem !is null && aItem.baseItem is bItem.baseItem)
					{
						duplicate = true;
						break;
					}
				}

				if (duplicate || newItem is null)
					continue;

				m_eqipmentChoices.insertLast(newItem);
			}
		}
		// HWP firearms: a Firearms Specialist's stock always holds a gun, a saved stock too (HWP/Firearms/Shops.as)
		{
			Equipment::Generator gunGen;
			gunGen.m_qualities = Item::Quality(int(Item::Quality::Uncommon) | int(Item::Quality::Rare));
			gunGen.m_ilvl = min(m_player.GetEquipmentDropLevelCap(), max(2, int(g_diffLevel + Modifiers::lerp(vec2(-1, 3), randf()))));
			HWP::Firearms::ShopNeedsGun(m_player, gunGen, m_eqipmentChoices);
		}

		float priceRate = 4.0f;
		array<IShopItem@> ret;
		for (uint i = 0; i < m_eqipmentChoices.length(); i++)
			ret.insertLast(EquipmentSellerShopContentItem(this, m_eqipmentChoices[i], i, ShopCost(MaterialType::Gold, int(m_eqipmentChoices[i].GetPrice() * priceRate))));
		return ret;
	}

	void Save(SValueBuilder& builder) override
	{
		builder.PushArray("choices");
		for (uint i = 0; i < m_eqipmentChoices.length(); i++)
			Item::SaveItem(builder, m_eqipmentChoices[i]);
		builder.PopArray();
	}
	
	void Load(SValue@ sval) override
	{
		auto choiceArr = GetParamArray(UnitPtr(), sval, "choices", false);
		if (choiceArr !is null)
		{
			m_eqipmentChoices.removeRange(0, m_eqipmentChoices.length());
			for (uint i = 0; i < choiceArr.length(); i++)
			{
				auto choice = cast<Equipment::Equipment>(Item::LoadItem(choiceArr[i]));
				if (choice !is null)
					m_eqipmentChoices.insertLast(choice);
			}
		}
	}
}