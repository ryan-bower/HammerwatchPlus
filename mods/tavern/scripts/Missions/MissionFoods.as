// HWP tavern (mods/tavern): vanilla's food and drink loadout (MissionFoods.as.orig) with
// more slots on the tavern's levels 4-6 (tweak/town/buildings/tavern.sval): drinks 1, 2, 3,
// 4, 4, 5 and food 1, 1, 1, 1, 2, 3 for levels 1-6. Food is a list like the drinks: the
// first food keeps vanilla's mission buff key ("food") and save entry, the others are
// "food1", "food2" and the save's "foods" array.

// slots for tavern level 1-6 (GetVariationOnBuilding("tavern") + 1); level 0: not built
int TavernDrinkSlots(int level)
{
	if (level >= 6)
		return 5;
	return level < 4 ? level : 4;
}

int TavernFoodSlots(int level)
{
	if (level >= 6)
		return 3;
	return level == 5 ? 2 : 1;
}

Item::Quality GetMaxTavernFoodQuality(int level)
{
	if (level == 0)
		return Item::Quality::Common;
	else if (level == 1)
		return Item::Quality::Uncommon;
	else if (level >= 2)
		return Item::Quality::Rare;
	
	return Item::Quality::None;
}

class SelectFoodLoadout : MissionGUILoadout
{
	array<MissionBuff@> m_currDrinks;
	array<MissionBuff@> m_currFoods;

	Widget@ m_groupW;
	Widget@ m_templateW;

	SelectFoodSelector@ m_selectFood;

	PlayerRecord@ m_player;
	int m_changingDrink;

	SelectFoodLoadout(SValue& params)
	{
		super(params);
	}
	
	bool BuildGUI(PlayerRecord@ plr, MissionLoadoutMenu@ menu, Widget@ segment, int yNavPos) override
	{
		if (!MissionGUILoadout::BuildGUI(plr, menu, segment, yNavPos))
			return false;
		
		@m_player = plr;
		@m_templateW = segment.GetWidgetById("template");
		auto container = segment.GetWidgetById("container");

		auto rect = cast<AInteractableWidget>(segment.GetWidgetById("rect").Clone());
		rect.m_visible = true;
		rect.m_func = m_id + " open";
		rect.m_navPos = ivec2(0, yNavPos);

		@m_groupW = rect.GetWidgetById("group");
		m_groupW.m_visible = true;

		container.AddChild(rect);

		UpdateIcons();

		return true;
	}

	void UpdateIcons()
	{
		// no row when the loadout menu skipped this loadout (its conditionals: a guild hall)
		if (m_groupW is null)
			return;

		m_groupW.ClearChildren();

		for (uint i = 0; i < m_currFoods.length(); i++)
		{
			auto buffW = m_templateW.Clone();
			buffW.m_visible = true;

			auto icon = cast<SpriteWidget>(buffW.GetWidgetById("icon"));
			icon.SetSprite(m_currFoods[i].m_icon);

			auto background = cast<SpriteWidget>(buffW);
			@background.m_sprite = null; // GetQualitySprite(m_currFoods[i].m_quality);

			m_groupW.AddChild(buffW);
		}

		for (uint i = 0; i < m_currDrinks.length(); i++)
		{
			auto drink = m_currDrinks[i];

			auto buffW = m_templateW.Clone();
			buffW.m_visible = true;

			auto icon = cast<SpriteWidget>(buffW.GetWidgetById("icon"));
			icon.SetSprite(drink.m_icon);

			auto background = cast<SpriteWidget>(buffW);
			@background.m_sprite = null; // GetQualitySprite(drink.m_quality);

			m_groupW.AddChild(buffW);
		}
	}

	void OnPlay() override
	{
		auto currentCost = GetCost();

		if (!currentCost.CanAfford(m_player))
			return;

		currentCost.Spend(m_player);

		for (uint i = 0; i < m_currFoods.length(); i++)
		{
			if (m_currFoods[i] is null)
				continue;

			m_player.SetMissionBuff(HashString(m_id + "food" + (i == 0 ? "" : ("" + i))), m_currFoods[i]);
		}

		for (uint i = 0; i < m_currDrinks.length(); i++)
		{
			if (m_currDrinks[i] is null)
				continue;

			m_player.SetMissionBuff(HashString(m_id + "drinks" + i), m_currDrinks[i]);
		}
	}

	ShopCost@ GetCost() override
	{
		auto cost = ShopCost();
		for (uint i = 0; i < m_currFoods.length(); i++)
		{
			if (m_currFoods[i] !is null)
				cost.AddCost(m_currFoods[i].m_cost);
		}

		for (uint i = 0; i < m_currDrinks.length(); i++)
		{
			if (m_currDrinks[i] is null)
				continue;

			cost.AddCost(m_currDrinks[i].m_cost);
		}

		return cost;
	}

	void UpdateMenuCost()
	{
		m_menu.RefreshCost();
	}

	bool UpdateTooltip(WindowManager@ manager) override
	{ 
		if (m_selectFood !is null)
			return m_selectFood.UpdateTooltip(manager);

		return false; 
	}

	void OnFunc(Widget@ sender, const string &in name) override
	{
		auto parse = name.split(" ");
		if (parse[1] == "open")
		{
			@m_selectFood = SelectFoodSelector(this);
			cast<BaseGameMode>(g_gameMode).m_windowManager.AddWindowObject(
				m_selectFood
			);
		}
	}


	void Save(SValueBuilder& builder) override 
	{
		builder.PushDictionary(m_id);
		// "food" is vanilla's one food (a save read without this mod keeps it)
		if (m_currFoods.length() > 0 && m_currFoods[0] !is null)
			builder.PushString("food", m_currFoods[0].m_id);

		builder.PushArray("foods");
		for (uint i = 0; i < m_currFoods.length(); i++)
		{
			if (m_currFoods[i] !is null)
				builder.PushString(m_currFoods[i].m_id);
		}
		builder.PopArray();

		builder.PushArray("drinks");
		for (uint i = 0; i < m_currDrinks.length(); i++)
		{
			if (m_currDrinks[i] !is null)
				builder.PushString(m_currDrinks[i].m_id);
		}
		builder.PopArray();
		builder.PopDictionary();
	}
	
	void Load(PlayerRecord@ plr, SValue@ save) override 
	{
		auto data = save.GetDictionaryEntry(m_id);
		if (data is null)
			return;
		
		auto tavernLevel = g_currTownRecord.GetVariationOnBuilding(HashString("tavern")) + 1;
		
		UnitPtr u;
		m_currFoods.removeRange(0, m_currFoods.length());
		array<string> foodIds;
		auto foodsArr = GetParamArray(u, data, "foods", false);
		if (foodsArr !is null)
		{
			for (uint i = 0; i < foodsArr.length(); i++)
				foodIds.insertLast(foodsArr[i].GetString());
		}
		else
			foodIds.insertLast(GetParamString(u, data, "food", false));

		for (uint i = 0; i < foodIds.length(); i++)
		{
			auto food = MissionBuff::Get(foodIds[i]);
			if (food !is null && m_currFoods.findByRef(food) == -1
				&& MissionBuff::IsValidMissionBuff(m_player, HashString("tavern_food"), GetMaxTavernFoodQuality(tavernLevel - 1), food))
				m_currFoods.insertLast(food);

			if (int(m_currFoods.length()) >= TavernFoodSlots(tavernLevel))
				break;
		}

auto drinksArr = GetParamArray(u, data, "drinks", false);
		if (drinksArr !is null)
		{
			m_currDrinks.removeRange(0, m_currDrinks.length());
			for (uint i = 0; i < drinksArr.length(); i++)
			{
				auto drink = MissionBuff::Get(drinksArr[i].GetString());
				if (MissionBuff::IsValidMissionBuff(m_player, HashString("tavern_drink"), GetMaxTavernFoodQuality(tavernLevel - 1), drink))
					m_currDrinks.insertLast(drink);
				
				if (int(m_currDrinks.length()) >= TavernDrinkSlots(tavernLevel))
					break;
			}
		}
	}
}

class SelectFoodSelector : AWindowObject
{
	array<MissionBuff@> m_currDrinks;
	array<MissionBuff@> m_currFoods;

	array<CheckBoxWidget@> m_foods;
	array<CheckBoxWidget@> m_drinks;

	Widget@ m_currentGroup;
	Widget@ m_currentTemplate;

	ITooltip@ m_selectedTooltip;
	Widget@ m_compareAnchor;
	AInteractableWidget@ m_currHover;

	TextWidget@ m_foodText;
	TextWidget@ m_drinkText;
	TextWidget@ m_costText;

	SelectFoodLoadout@ m_host;

	int m_tavernLevel;
	bool m_changed;

	SelectFoodSelector(SelectFoodLoadout@ host)
	{
		super(g_gameMode.m_guiBuilder, "gui/mission_loadout/food_drink_picker.gui");

		m_tavernLevel = g_currTownRecord.GetVariationOnBuilding(HashString("tavern")) + 1;

		@m_host = host;
		@m_compareAnchor = m_widget.GetWidgetById("compare-anchor");
		@m_currentGroup = m_widget.GetWidgetById("current");
		@m_currentTemplate = m_widget.GetWidgetById("current-template");

		auto template = m_widget.GetWidgetById("template");
		auto scroll = m_widget.GetWidgetById("scroll");

		@m_foodText = cast<TextWidget>(m_widget.GetWidgetById("foods"));
		@m_drinkText = cast<TextWidget>(m_widget.GetWidgetById("drinks"));
		@m_costText = cast<TextWidget>(m_widget.GetWidgetById("cost"));


		int rowAmount = (scroll.m_width - int(scroll.m_padding.x * 2) - scroll.m_spacing) / template.m_width;
		int row = -1;
		int column = 0;

		auto foods = MissionBuff::GetMissionBuffs(m_host.m_player, HashString("tavern_food"), GetMaxTavernFoodQuality(m_tavernLevel - 1));
		for (uint i = 0; i < foods.length(); i++)
		{
			auto buff = template.Clone();
			buff.m_visible = true;
			buff.SetID("food");

			auto checkbox = cast<CheckBoxWidget>(buff.GetWidgetById("button"));
			checkbox.SetID(foods[i].m_id);
			checkbox.SetChecked(m_host.m_currFoods.findByRef(foods[i]) != -1);

			row++;
			if (row >= rowAmount)
			{
				row = 0;
				column++;
			}

			checkbox.m_navPos = ivec2(row, column);
			
			auto sprite = cast<SpriteWidget>(buff.GetWidgetById("icon"));
			sprite.SetSprite(foods[i].m_icon);

			auto background = cast<SpriteWidget>(buff.GetWidgetById("background"));
			background.SetSprite(GetQualitySprite(foods[i].m_quality));

			scroll.AddChild(buff);
			m_foods.insertLast(checkbox);
		}

		auto drinks = MissionBuff::GetMissionBuffs(m_host.m_player, HashString("tavern_drink"), GetMaxTavernFoodQuality(m_tavernLevel - 1));
		for (uint i = 0; i < drinks.length(); i++)
		{
			auto buff = template.Clone();
			buff.m_visible = true;
			buff.SetID("drink");
			
			auto checkbox = cast<CheckBoxWidget>(buff.GetWidgetById("button"));
			checkbox.SetID(drinks[i].m_id);
			checkbox.SetChecked(m_host.m_currDrinks.findByRef(drinks[i]) != -1);

			row++;
			if (row >= rowAmount)
			{
				row = 0;
				column++;
			}

			checkbox.m_navPos = ivec2(row, column);

			auto sprite = cast<SpriteWidget>(buff.GetWidgetById("icon"));
			sprite.SetSprite(drinks[i].m_icon);

			auto background = cast<SpriteWidget>(buff.GetWidgetById("background"));
			background.SetSprite(GetQualitySprite(drinks[i].m_quality));

			scroll.AddChild(buff);
			m_drinks.insertLast(checkbox);
		}

		for (uint i = 0; i < m_host.m_currDrinks.length(); i++)
			m_currDrinks.insertLast(m_host.m_currDrinks[i]);

		for (uint i = 0; i < m_host.m_currFoods.length(); i++)
			m_currFoods.insertLast(m_host.m_currFoods[i]);

		UpdateCurrentVisuals();

		@m_input.m_menuAdditionalOnPressed = WindowInput::OnFunc(this.Apply);
	}

	void RefreshKeybinds(ControlMap@ currMap) override
	{
		if (m_navigationBar is null)
			return;

		auto currInteractable = m_input.GetCurrentInteractable();
		if (currInteractable is null)
			return;

		array<string>@ rawTexts = currInteractable.NavigationBarText();
		array<KeyNavigationText@> navTexts;
		for (uint i = 0; i < rawTexts.length(); i++)
			navTexts.insertLast(KeyNavigationText(m_navigationBar.m_font.BuildText(rawTexts[i])));

		navTexts.insertLast(KeyNavigationText(m_navigationBar.m_font.BuildText(FormatKeyName(GetActionBinding("MenuAdditional")) + " " + Resources::GetString(".menu.nav.apply")), WindowInput::OnFunc(this.Apply)));

		m_navigationBar.BuildBar(navTexts, this);
	}

	void OnInteractableIndexChanged() override
	{
		auto currInteractable = m_input.GetCurrentInteractable();
		if (currInteractable is null)
			return;

		array<string>@ rawTexts = currInteractable.NavigationBarText();
		array<KeyNavigationText@> navTexts;
		for (uint i = 0; i < rawTexts.length(); i++)
			navTexts.insertLast(KeyNavigationText(m_navigationBar.m_font.BuildText(rawTexts[i])));

		navTexts.insertLast(KeyNavigationText(m_navigationBar.m_font.BuildText(FormatKeyName(GetActionBinding("MenuAdditional")) + " " + Resources::GetString(".menu.nav.apply")), WindowInput::OnFunc(this.Apply)));

		m_navigationBar.BuildBar(navTexts, this);
	}

	void Draw(SpriteBatch& sb, int idt) override
	{
		AWindowObject::Draw(sb, idt);

		if (m_selectedTooltip !is null)
		{
			vec2 ttPos = m_compareAnchor.m_origin;
			m_selectedTooltip.Draw(sb, ttPos);
		}
	}

	void UpdateCurrentVisuals()
	{
		m_currentGroup.ClearChildren();

		auto cost = ShopCost();
		for (uint i = 0; i < m_currFoods.length(); i++)
		{
			auto food = m_currFoods[i];
			cost.AddCost(food.m_cost);

			auto template = m_currentTemplate.Clone();
			template.m_visible = true;

			auto icon = cast<SpriteWidget>(template.GetWidgetById("icon"));
			icon.SetSprite(food.m_icon);

			//auto background = cast<SpriteWidget>(template);
			//@background.m_sprite = GetQualitySprite(food.m_quality);

			m_currentGroup.AddChild(template);
		}

		for (uint i = 0; i < m_currDrinks.length(); i++)
		{
			auto drink = m_currDrinks[i];
			cost.AddCost(drink.m_cost);

			auto template = m_currentTemplate.Clone();
			template.m_visible = true;

			auto icon = cast<SpriteWidget>(template.GetWidgetById("icon"));
			icon.SetSprite(drink.m_icon);

			//auto background = cast<SpriteWidget>(template);
			//@background.m_sprite = GetQualitySprite(drink.m_quality);

			m_currentGroup.AddChild(template);
		}

		m_foodText.SetText(Resources::GetString(".menu.loadout.food") + m_currFoods.length() + "/" + TavernFoodSlots(m_tavernLevel));
		m_drinkText.SetText(Resources::GetString(".menu.loadout.drinks") + m_currDrinks.length() + "/" + TavernDrinkSlots(m_tavernLevel));

		m_costText.SetText(cost.GetText(m_host.m_player));
	}

	void UpdateSelectedTooltip()
	{
		string title = Resources::GetString(".menu.loadout.alterations");
		string description;

		for (uint i = 0; i < m_currFoods.length(); i++)
		{
			description += m_currFoods[i].m_description;
			description += "\n\n";
		}

		for (uint i = 0; i < m_currDrinks.length(); i++)
		{
			description += m_currDrinks[i].m_description;
			description += "\n\n";
		}

		if (description.isEmpty())
		{
			@m_selectedTooltip = null;
			return;
		}

		@m_selectedTooltip = CreateTitledTooltip(
			Resources::GetSValue("gui/variable/itemtooltip_common.sval"), 
			title, 
			description,
			null,
			null
		);
	}

	bool UpdateTooltip(WindowManager@ manager)
	{
		if (m_currHover is null)
			return false;

		if (!m_currHover.m_hovering)
			return false;

		MissionBuff@ buff = MissionBuff::Get(m_currHover.m_id);
		if (buff is null)
			return false;

		auto iconFrame = ScriptSprite(Resources::GetTexture2D("gui/gui.png"), vec4(76, 210, 28, 28));
		m_manager.SetTooltip(
			CreateTitledTooltip(Resources::GetSValue("gui/variable/itemtooltip_common.sval"), 
				buff.m_name,  buff.m_description, buff.m_icon, iconFrame, buff.m_quality)
		, true);

		return true;
	}

	// as AddDrink: past the slots the oldest pick goes
	void AddFood(MissionBuff@ food)
	{
		m_currFoods.insertLast(food);

		while (int(m_currFoods.length()) > TavernFoodSlots(m_tavernLevel))
			m_currFoods.removeAt(0);
	}

	void RemoveFood(MissionBuff@ food)
	{
		int i = m_currFoods.findByRef(food);
		if (i == -1)
			return;

		m_currFoods.removeAt(i);
	}

	void AddDrink(MissionBuff@ drink)
	{
		m_currDrinks.insertLast(drink);

		while (int(m_currDrinks.length()) > TavernDrinkSlots(m_tavernLevel))
			m_currDrinks.removeAt(0);
	}

	void RemoveDrink(MissionBuff@ drink)
	{
		int i = m_currDrinks.findByRef(drink);
		if (i == -1)
			return;

		m_currDrinks.removeAt(i);
	}

	void Apply()
	{
		m_host.m_currDrinks.removeRange(0, m_host.m_currDrinks.length());

		for (uint i = 0; i < m_currDrinks.length(); i++)
			m_host.m_currDrinks.insertLast(m_currDrinks[i]);

		m_host.m_currFoods.removeRange(0, m_host.m_currFoods.length());

		for (uint i = 0; i < m_currFoods.length(); i++)
			m_host.m_currFoods.insertLast(m_currFoods[i]);

		m_host.UpdateIcons();
		m_host.UpdateMenuCost();

		m_manager.CloseTooltip();

		m_changed = false;
		m_closing = true;
	}

	bool Back() override
	{
		if (m_changed)
		{
			//g_gameMode.ShowDialog("exit", Resources::GetString(".option.prompt.settings_appy"), Resources::GetString(".menu.nav.save"), Resources::GetString(".menu.nav.revert"), this);
			Apply();
			return false;
		}

		@m_host.m_selectFood = null;
		return true;
	}

	void OnFunc(Widget@ sender, const string &in name) override
	{
		if (name == "hover")
		{
			MissionBuff@ buff = MissionBuff::Get(sender.m_id);

			auto iconFrame = ScriptSprite(Resources::GetTexture2D("gui/gui.png"), vec4(76, 210, 28, 28));
			m_manager.SetTooltip(
				CreateTitledTooltip(Resources::GetSValue("gui/variable/itemtooltip_common.sval"), 
					buff.m_name,  buff.m_description, buff.m_icon, iconFrame, buff.m_quality)
			, true);

			@m_currHover = cast<AInteractableWidget>(sender);
		}
		else if (name == "select")
		{
			if (sender.m_parent.m_id == "food")
			{
				MissionBuff@ buff = MissionBuff::Get(sender.m_id);
				if (m_currFoods.findByRef(buff) == -1)
					AddFood(buff);
				else
					RemoveFood(buff);

				for (uint i = 0; i < m_foods.length(); i++)
				{
					auto food = MissionBuff::Get(m_foods[i].m_id);
					m_foods[i].SetChecked(m_currFoods.findByRef(food) != -1);
				}
			}
			else
			{
				MissionBuff@ buff = MissionBuff::Get(sender.m_id);
				if (m_currDrinks.findByRef(buff) == -1)
					AddDrink(buff);
				else
					RemoveDrink(buff);

				for (uint i = 0; i < m_drinks.length(); i++)
				{
					auto drink = MissionBuff::Get(m_drinks[i].m_id);
					bool checked = m_currDrinks.findByRef(drink) != -1;
					m_drinks[i].SetChecked(checked);
				}
			}

			m_changed = true;
			UpdateCurrentVisuals();
			UpdateSelectedTooltip();
		}
		else if (name == "exit yes")
			Apply();
		else if (name == "exit no")
			m_closing = true;
	}
}