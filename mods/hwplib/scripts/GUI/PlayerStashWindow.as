class PlayerStashWindow : AWindowObject
{
	PlayerRecord@ m_record;
	TownStash@ m_townStash;
	TownStashTab@ m_currTownStashTab;

	TextWidget@ m_tabSelector;
	MenuTabGroupWidget@ m_tabsMode;

	array<string> m_tabNames;
	uint m_tabIndex;

	Widget@ m_equipmentGroupWidget;
	StashInventoryWidget@ m_stashInventoryWidget;
	StashInventoryWidget@ m_playerInventoryWidget;

	Equipment::Equipment@ m_deletingEquipment;

	Widget@ m_withdrawContent;
	Widget@ m_depositContent;

	PlayerStashWindow(GUIBuilder@ b, WindowManager@ manager, PlayerRecord@ record, TownStash@ stash)
	{
		super(b, "gui/player_stash/player_stash.gui");

		@m_playerInventoryWidget = cast<StashInventoryWidget>(m_widget.GetWidgetById("player-inventory"));
		@m_playerInventoryWidget.m_itemTemplate = cast<StashItemWidget>(m_widget.GetWidgetById("player-item-template"));
		@m_playerInventoryWidget.m_window = this;

		@m_stashInventoryWidget = cast<StashInventoryWidget>(m_widget.GetWidgetById("stash-inventory"));
		@m_stashInventoryWidget.m_itemTemplate = cast<StashItemWidget>(m_widget.GetWidgetById("stash-item-template"));
		@m_stashInventoryWidget.m_window = this;

		@m_equipmentGroupWidget = m_widget.GetWidgetById("equipment-group");

		@m_tabSelector = cast<TextWidget>(m_widget.GetWidgetById("tab-picks"));

		@m_tabsMode = cast<MenuTabGroupWidget>(m_widget.GetWidgetById("tabs-mode"));
		m_tabsMode.SetChecked(0);

		@m_manager = manager;
		@m_record = record;
		@m_townStash = stash;

		@m_withdrawContent = m_widget.GetWidgetById("withdraw-content");
		@m_depositContent = m_widget.GetWidgetById("deposit-content");

		BuildTabs();
		SetMode(HashString("withdraw-content"));

		@m_input.m_menuContextOnPressed = WindowInput::OnFunc(this.MenuContext);
		@m_input.m_menuAdditionalOnPressed = WindowInput::OnFunc(this.MenuAdditional);
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

		m_navigationBar.BuildBar(navTexts, this);

		if (m_withdrawContent !is null && m_withdrawContent.m_visible)
		{
			if (m_navigationBar.m_texts.length() > 1)
				m_navigationBar.m_texts.insertAt(1, KeyNavigationText(m_navigationBar.m_font.BuildText(FormatKeyName(GetActionBinding("PlayerMenu")) + " " + Resources::GetString(".menu.nav.stash_config")), WindowInput::OnFunc(this.ShowConfiguration)));
			else
				m_navigationBar.m_texts.insertLast(KeyNavigationText(m_navigationBar.m_font.BuildText(FormatKeyName(GetActionBinding("PlayerMenu")) + " " + Resources::GetString(".menu.nav.stash_config")), WindowInput::OnFunc(this.ShowConfiguration)));
		}
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

		m_navigationBar.BuildBar(navTexts, this);

		if (m_withdrawContent !is null && m_withdrawContent.m_visible)
		{
			if (m_navigationBar.m_texts.length() > 1)
				m_navigationBar.m_texts.insertAt(1, KeyNavigationText(m_navigationBar.m_font.BuildText(FormatKeyName(GetActionBinding("PlayerMenu")) + " " + Resources::GetString(".menu.nav.stash_config")), WindowInput::OnFunc(this.ShowConfiguration)));
			else
				m_navigationBar.m_texts.insertLast(KeyNavigationText(m_navigationBar.m_font.BuildText(FormatKeyName(GetActionBinding("PlayerMenu")) + " " + Resources::GetString(".menu.nav.stash_config")), WindowInput::OnFunc(this.ShowConfiguration)));
		}
	}

	Equipment::Equipment@ GetHoveringEquipment()
	{
		Item::Item@ item;

		auto inventoryScroll = cast<ScrollbarWidget>(m_input.GetCurrentInteractable());
		if (inventoryScroll !is null)
		{
			auto stashItem = cast<StashItemWidget>(inventoryScroll.m_input.GetCurrentInteractable());
			if (stashItem is null)
				return null;

			if (stashItem.m_item !is null)
				@item = stashItem.m_item;
		}

		if (item is null)
		{
			auto hoveringItem = cast<StashItemWidget>(m_input.GetCurrentInteractable());
			if (hoveringItem !is null)
				@item = hoveringItem.m_item;
		}

		if (item is null)
			return null;

		return cast<Equipment::Equipment>(item);
	}

	void ShowConfiguration()
	{
		m_manager.CloseTooltip();
		m_manager.AddWindowObject(PlayerStashEditWindow(m_builder, m_manager, this));
	}

	void MenuContext()
	{
		auto hoveringEquipment = GetHoveringEquipment();
		if (hoveringEquipment is null)
			return;

		if (cast<CompareItemTooltip>(m_manager.m_tooltip) !is null)
			m_manager.SetTooltip(Item::BuildItemTooltip(hoveringEquipment, hoveringEquipment.GetPrice(), 1, false), true);
		else
			m_manager.SetTooltip(Item::BuildCompareItemTooltip(hoveringEquipment, hoveringEquipment.GetPrice()), true);
	}

	void MenuAdditional()
	{
		@m_deletingEquipment = GetHoveringEquipment();
		if (m_deletingEquipment is null)
			return;

		m_manager.CloseTooltip();
		g_gameMode.ShowDialog("destroy",
			HWP::ItemActions::DestroyConfirm(m_deletingEquipment),   // HammerwatchPlus: a mod's Destroy (salvage)
			Resources::GetString(".menu.yes"),
			Resources::GetString(".menu.no"),
			this
		);
	}

	void BuildTabs()
	{
		m_tabNames.resize(0);
		m_tabIndex = 0;
		for (uint i = 0; i < m_townStash.m_tabs.length(); i++)
			m_tabNames.insertLast(m_townStash.m_tabs[i].m_name);

		if (m_tabNames.length() > 0)
			m_tabSelector.SetText(m_tabNames[m_tabIndex]);
		else
			m_tabSelector.SetText("");
	}

	void CreateNewTab(TownStashTab@ townStashTab)
	{
		m_tabNames.insertLast(townStashTab.m_name);

		SetTab(m_tabNames.length() - 1);

		SaveStash();
	}

	void RemoveCurrentTab()
	{
		if (m_currTownStashTab is null)
			return;

		if (!m_townStash.Remove(m_currTownStashTab))
			return;

		BuildTabs();
		SetTab(0);

		SaveStash();
	}

	void RenameCurrentTab(const string &in name)
	{
		if (m_currTownStashTab is null)
			return;

		m_currTownStashTab.m_name = name;
		m_tabNames[m_tabIndex] = name;
		UpdateTabName();

		Refresh();

		SaveStash();
	}

	void Refresh(bool refreshInteractables = true)
	{
		@m_deletingEquipment = null;

		for (uint i = 0; i < m_equipmentGroupWidget.m_children.length(); i++)
		{
			auto child = cast<StashItemWidget>(m_equipmentGroupWidget.m_children[i]);

			child.Clear();

			auto slot = StringToEquippedItemsSlots(child.m_id);
			if (slot == EquippedItemsSlots::OffHand && m_record.equipped.m_items[EquippedItemsSlots::MainHand] !is null && 
				m_record.equipped.m_items[EquippedItemsSlots::MainHand].GetSlot() == Equipment::Slot::TwoHanded)
			{
				child.m_color = child.m_disabledColor;
				child.m_mirroredIcon = true;
				child.Set(m_record.equipped.GetEquipment(EquippedItemsSlots::MainHand));
			}
			else
			{
				child.m_color = vec4(1.0f);
				child.m_mirroredIcon = false;
				child.Set(m_record.equipped.GetEquipment(slot));
			}
		}

		@m_currTownStashTab = m_townStash.m_tabs[m_tabIndex];
		m_playerInventoryWidget.Set(m_record.equipInventory.m_items);
		m_stashInventoryWidget.Set(m_currTownStashTab.m_items);

		if (refreshInteractables)
			m_input.RefreshInteractableWidgets(m_widget);
	}

	void UpdateTabName()
	{
		if (m_tabNames.length() == 0)
		{
			m_tabSelector.SetText("");
			return;
		}

		m_tabSelector.SetText(m_tabNames[m_tabIndex]);
	}

	void SetTab(uint i)
	{
		if (m_tabNames.length() == 0)
			return;

		CloseTooltip();

		if (i >= m_tabNames.length())
			i = 0;

		m_tabIndex = i;
		UpdateTabName();

		Refresh();
	}

	void StepTab(int i)
	{
		CloseTooltip();

		if (i > 0)
			SetTab(m_tabIndex + 1);
		else
		{
			if (m_tabIndex == 0)
				SetTab(m_tabNames.length() - 1);
			else
				SetTab(m_tabIndex - 1);
		}

		Refresh();
	}

	void SetMode(uint i)
	{
		m_manager.CloseTooltip();

		if (m_withdrawContent.m_idHash == i)
		{
			m_withdrawContent.m_visible = true;
			m_depositContent.m_visible = false;
		}
		else if (m_depositContent.m_idHash == i)
		{
			m_withdrawContent.m_visible = false;
			m_depositContent.m_visible = true;
		}

		Refresh();
	}

	void StepMode(int i)
	{
		m_manager.CloseTooltip();

		m_tabsMode.StepChecked(i > 0);
		SetMode(HashString(m_tabsMode.GetChecked().GetValue()));
	}

	void CloseTooltip()
	{
		BaseGameMode@ gm = cast<BaseGameMode>(g_gameMode);
		if (gm !is null)
			gm.m_windowManager.CloseTooltip();
	}

	bool Update(int ms, GameInput& gameInput, MenuInput& menuInput) override
	{
		bool ret = AWindowObject::Update(ms, gameInput, menuInput);

%if GAME
		if (menuInput.MenuPreviousTab.Pressed)
			StepMode(-1);
		else if (menuInput.MenuNextTab.Pressed)
			StepMode(1);

		if (m_withdrawContent.m_visible)
		{
			if (menuInput.MenuPreviousSubTab.Pressed)
				StepTab(-1);
			else if (menuInput.MenuNextSubTab.Pressed)
				StepTab(1);
			else if (gameInput.PlayerMenu.Pressed)
				ShowConfiguration();
		}
%endif

		return ret;
	}

	void Draw(SpriteBatch& sb, int idt) override
	{
		AWindowObject::Draw(sb, idt);
	}

	void OnClose() override
	{
		SaveStash();
	}

	void SaveStash()
	{
		cast<AGameplayGameMode>(g_gameMode).SavePlayerAndTown();
	}

	void OnFunc(Widget@ sender, const string &in name) override
	{
		print("PlayerStashWindow::" + name);
		auto parse = name.split(" ");
		if (parse[0] == "set-mode")
			SetMode(HashString(parse[1]));
		else if (parse[0] == "withdraw")
		{
			auto itemWidget = cast<StashItemWidget>(sender);
			if (itemWidget is null)
				return;

			auto item = cast<Equipment::Equipment>(itemWidget.m_item);

			if (!m_record.CanAddItem(item))
				return;

			if (!m_currTownStashTab.Remove(item))
				return;

			m_record.equipInventory.Add(item);
			Refresh();
			SaveStash();
		}
		else if (parse[0] == "deposit")
		{
			auto itemWidget = cast<StashItemWidget>(sender);
			if (itemWidget is null)
				return;

			auto item = cast<Equipment::Equipment>(itemWidget.m_item);

			if (parse[1] == "equipped" && !m_record.equipped.Unequip(item))
				return;
			else if (parse[1] == "inventory" && !m_record.equipInventory.Remove(item))
				return;

			m_currTownStashTab.Add(item);
			Refresh(false);
			SaveStash();
		}
		else if (parse[0] == "destroy")
		{
			if (parse[1] == "yes")
			{
				if (m_deletingEquipment !is null)
				{
					if (m_record.equipped.Unequip(m_deletingEquipment) || m_record.equipInventory.Remove(cast<Equipment::Equipment>(m_deletingEquipment)) || m_currTownStashTab.Remove(m_deletingEquipment))
					{
						print("destroyed " + m_deletingEquipment.GetName());
						HWP::ItemActions::Destroyed(m_record, m_deletingEquipment);   // HammerwatchPlus: salvage
					}

					Refresh(false);
					SaveStash();
				}
				else
					PrintError("Failed to find an item to delete.");
			}
		}
		else if (parse[0] == "button")
		{
			if (parse[1] == "right")
				StepTab(1);
			else if (parse[1] == "left")
				StepTab(-1);
		}
		else
			Refresh();
	}
}