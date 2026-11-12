namespace Equipment
{
	class UniqueEquipment : Equipment, SVO
	{
		array<uint> m_tags;
		Slot m_slot;
		Item::Quality m_quality;
		int m_price;

		array<Modifiers::IModifier@> m_modifiers;
		Item::ItemSkillDef@ m_skill;
		Item::ItemSkillDef@ m_skill2;
		
		string m_name;
		string m_desc;
		
		string m_graphic;
		Model@ m_model;
		ScriptSprite@ m_icon;
		
		int m_dropChance;

		Slot GetSlot() override { return m_slot; }
		array<Modifiers::IModifier@>@ GetModifiers() override { return m_modifiers; }
		bool HasAnyTag(array<uint>@ tags) override { return MatchTags(m_tags, tags); }
	
		bool SVO_Init_Post(SValue& params) 
		{
			UnitPtr u;
			m_modifiers = Modifiers::LoadIModifiers(u, params, Modifiers::SlotToRole(m_slot), "", Modifiers::SyncVerb::Item, m_idHash);
			return true;
		}
	
		UniqueEquipment(SValue& params)
		{
			super();
			
			UnitPtr u();

			m_name = Resources::GetString(GetParamString(u, params, "name"));
			m_desc = Resources::GetString(GetParamString(u, params, "desc", false));
			m_slot = ParseItemSlot(GetParamString(u, params, "slot"));
			m_quality = Item::ParseQuality(GetParamString(u, params, "quality"));
			m_price = GetParamInt(u, params, "price", false, 0);
			m_graphic = GetParamString(u, params, "graphic", false);
			m_dropChance = GetParamInt(u, params, "drop-rate", false, 100);
			
			@m_skill = Item::ItemSkillDef::Get(GetParamString(u, params, "skill", false));
			@m_skill2 = Item::ItemSkillDef::Get(GetParamString(u, params, "skill-secondary", false));
			
			auto modelStr = GetParamString(u, params, "model", false);
			if (!modelStr.isEmpty())
				@m_model = Resources::GetModel(modelStr);
			
			
			auto iconArr = GetParamArray(u, params, "icon", false);
			if (iconArr is null)
				@m_icon = ScriptSprite(Resources::GetTexture2D("items/icons_equipment.png"), vec4(48, 24, 24, 24));
			else
				@m_icon = ScriptSprite(iconArr);
			
			
			array<SValue@>@ tagArr = GetParamArray(u, params, "tags");
			for (uint i = 0; i < tagArr.length(); i++)
				m_tags.insertLast(HashString(tagArr[i].GetString()));
		}

		UniqueEquipment() { super(); }
		
		Item::Item@ Copy() override 
		{
			// Owned copies need distinct identity for per-piece favorites.
			auto item = UniqueEquipment();
			item = this;
			return item;
		}

		void Save(SValueBuilder& builder) override
		{
			//builder.PushInteger(m_idHash);
			builder.PushString(m_id);
		}
		
		
		string& GetName() override { return m_name; }
		string& GetDescription(PlayerRecord@ plr) override { return m_desc; }
		uint GetIDHash() override { return m_idHash; }
		
		string& GetGraphic() override { return m_graphic; }
		Model@ GetModel() override { return m_model; }
		Item::Quality GetQuality() override { return m_quality; }
		ScriptSprite@ GetIcon() override { return m_icon; }
		bool IsEquippable() override { return true; }
		int GetPrice() override { return m_price; }
		Item::ItemSkillDef@ GetSkill() override { return m_skill; }
		Item::ItemSkillDef@ GetSecondarySkill() override { return m_skill2; }
	}

}
