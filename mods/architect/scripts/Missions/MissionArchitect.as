// HWP override of scripts/Missions/MissionArchitect.as (see mods/architect/README.md).
// Every change is marked HWP; pristine copy: MissionArchitect.as.orig
float CalcArchitectCostMul(int numBuffs, int numDebuffs)
{
	float mul = 1.0f;
	
	int archLvl = g_currTownRecord.GetVariationOnBuilding(HashString("architect"));
	
	if (archLvl >= 1)
		mul = (pow(float(max(1, numBuffs)), 1.6f) - 1) / 7.0f + 1.0f;
	else
		mul = (pow(float(max(1, numBuffs)), 1.8f) - 1) / 6.0f + 1.0f;
	
	mul -= pow(float(numDebuffs), 1.5f) / 2.0f;
	
	return max(0.0f, mul);
}

class SelectArchitectLoadout : MissionGUILoadout
{
	PlayerRecord@ m_player;
	Widget@ m_scroll;
	Widget@ m_buffTemplate;
	uint32 m_buffSet;
	
	array<uint> m_buffs;
	array<uint8> m_payers; // HWP: peer that pays for m_buffs[i] (0 = host, split when architect.split is on)


	SelectArchitectLoadout(SValue& params)
	{
		super(params);
		
		m_buffSet = HashString(GetParamString(UnitPtr(), params, "buff-set", true));
	}


	bool BuildGUI(PlayerRecord@ plr, MissionLoadoutMenu@ menu, Widget@ segment, int yNavPos) override
	{
		auto currMissionDef = MissionDef::Get(MissionManager::g_module.m_missionDefHash);
		if (currMissionDef is null || (currMissionDef.m_id != "dark_citadel" && currMissionDef.m_id != "mega_dungeon"))
			return false;
		
		if (!MissionGUILoadout::BuildGUI(plr, menu, segment, yNavPos))
			return false;
		
		@m_player = plr;
		@m_buffTemplate = segment.GetWidgetById("template-buff");
		auto container = segment.GetWidgetById("container");

		auto rect = cast<AInteractableWidget>(segment.GetWidgetById("rect").Clone());
		rect.m_visible = true;
		rect.m_func = m_id + " open";
		// HWP: every player may pick (and pay for) alterations; the host only with the module off
		rect.m_enabled = Network::IsServer() || HWP::Architect::Enabled();
		rect.m_navPos = ivec2(0, yNavPos);

		auto group = rect.GetWidgetById("group");
		auto scroll = group.GetWidgetById("scroll");
		@m_scroll = scroll;
		
		// HWP: pull the party's current picks from the host. On the host the
		// request is answered synchronously - before this menu is registered
		// with the window manager, so the sync cannot find it - hence the list
		// is seeded from the synced state right here on every machine.
		HWP::Architect::RequestState();
		// HWP: with none of my picks in the party's list (a fresh setup), the picks I had
		// last time come back (architect.last on my record; the host merges them as a
		// pick, synchronously on the host, by architect.sync on a client)
		if (HWP::Architect::Enabled() && HWP::Architect::MyPicks().length() == 0)
		{
			auto last = HWP::Architect::Available(HWP::Architect::LastPicks(), plr, m_buffSet);
			if (last.length() > 0)
			{
				HWP::Architect::SendPicks(last);
				HWP::Log("architect", "restored " + last.length() + " remembered pick(s)");
			}
		}
		m_buffs.removeRange(0, m_buffs.length());
		m_payers.removeRange(0, m_payers.length());
		for (uint i = 0; i < HWP::Architect::g_ids.length(); i++)
		{
			m_buffs.insertLast(uint(HWP::Architect::g_ids[i]));
			m_payers.insertLast(uint8(i < HWP::Architect::g_payers.length() ? HWP::Architect::g_payers[i] : 0));
		}

		int width = 0;
		for (uint i = 0; i < m_buffs.length(); i++)
		{
			auto buff = MissionBuff::Get(m_buffs[i]);
			if (buff is null) // HWP: unknown id from a mismatched mod version
				continue;

			auto buffW = m_buffTemplate.Clone();
			buffW.m_visible = true;
			buffW.SetID(buff.m_id);

			auto text = cast<TextWidget>(buffW);
			text.SetText(HWPBuffLabel(i)); // HWP: "- name (payer)"
			text.m_width = scroll.m_width / 2;
			
			scroll.AddChild(buffW);
			width += buffW.m_width;
		}
		
		container.AddChild(rect);
		m_width = max(m_width, width);
		
		if (MissionBuff::GetMissionBuffs(plr, m_buffSet).length() <= 0)
			return false;
		
		return true;
	}

	void Refresh()
	{
		m_scroll.ClearChildren();

		for (uint i = 0; i < m_buffs.length(); i++)
		{
			auto buff = MissionBuff::Get(m_buffs[i]);
			if (buff is null) // HWP
				continue;

			auto buffW = m_buffTemplate.Clone();
			buffW.m_visible = true;
			buffW.SetID(buff.m_id);

			auto text = cast<TextWidget>(buffW);
			text.SetText(HWPBuffLabel(i)); // HWP: "- name (payer)"
			text.m_width = m_scroll.m_width / 2;
			
			m_scroll.AddChild(buffW);
		}

		m_menu.RefreshCost();
	}

	void OnPlay() override
	{
		// HWP: everyone pays their own share - sponsored picks in full, the
		// host's picks split evenly across the party when architect.split is on.
		auto cost = CalcMyCost();
		HWP::Architect::OnMissionStarted();

		if (!cost.CanAfford(m_player))
		{
			// The menu hides Ready while the share is unaffordable and un-readies
			// a player whose share changes, so this is a force start racing a
			// pick. Nobody gets alterations they did not pay for, and nobody
			// goes negative.
			HWP::LogError("architect", m_player.GetName() + " cannot afford the architect share at start; alterations skipped");
			return;
		}

		if (Network::IsServer())
			cost.Spend(m_player);
		else
		{
			for (uint j = 0; j < cost.m_cost.length(); j += 2)
				m_player.materials[cost.m_cost[j]] -= cost.m_cost[j + 1];
		}

		for (uint i = 0; i < m_buffs.length(); i++)
		{
			auto missionBuff = MissionBuff::Get(m_buffs[i]);
			if (missionBuff is null)
				continue;
			
			m_player.architectBuffs.insertLast(missionBuff);
		}
	}

	ShopCost@ GetCost() override
	{
		return CalcMyCost(); // HWP: the local player's share, on clients too
	}

	// HWP: what the local player pays. Cost multiplier counts every pick no
	// matter who pays, like vanilla; like vanilla it applies to the summed
	// cost (own picks, and the split picks), so solo matches vanilla to the
	// gold piece; shares round up. A challenge's fixed discount comes off the
	// bill of whoever pays for its slot (the split pool for the host's picks)
	// after the multiplier, and a material stops at 0.
	ShopCost@ CalcMyCost()
	{
		float mul = HWP::Architect::CostMul(m_buffs);

		uint8 me = uint8(m_player.peer);
		int players = HWP::Architect::ActivePlayers();
		auto own = ShopCost();
		auto pooled = ShopCost();
		auto ownOff = ShopCost();
		auto pooledOff = ShopCost();
		for (uint i = 0; i < m_buffs.length(); i++)
		{
			auto missionBuff = MissionBuff::Get(m_buffs[i]);
			if (missionBuff is null)
				continue;
			uint8 payer = i < m_payers.length() ? m_payers[i] : 0;
			bool split = payer == 0 && HWP::Architect::g_split && players > 1;
			if (!split && payer != me)
				continue;

			auto discount = HWP::Architect::ChallengeDiscount(m_buffs[i]);
			if (discount !is null)
			{
				if (split)
					pooledOff.AddCost(discount);
				else
					ownOff.AddCost(discount);
				continue;
			}

			for (uint j = 0; j + 1 < missionBuff.m_cost.m_cost.length(); j += 2)
			{
				if (split)
					pooled.AddCost(MaterialType(missionBuff.m_cost.m_cost[j]), missionBuff.m_cost.m_cost[j + 1]);
				else
					own.AddCost(MaterialType(missionBuff.m_cost.m_cost[j]), missionBuff.m_cost.m_cost[j + 1]);
			}
		}

		auto cost = ShopCost();
		for (uint j = 0; j + 1 < own.m_cost.length(); j += 2)
		{
			int amount = int(own.m_cost[j + 1] * mul) - ownOff.GetCost(MaterialType(own.m_cost[j]));
			if (amount > 0)
				cost.AddCost(MaterialType(own.m_cost[j]), amount);
		}
		for (uint j = 0; j + 1 < pooled.m_cost.length(); j += 2)
		{
			int left = int(pooled.m_cost[j + 1] * mul) - pooledOff.GetCost(MaterialType(pooled.m_cost[j]));
			int amount = (left + players - 1) / players;
			if (amount > 0)
				cost.AddCost(MaterialType(pooled.m_cost[j]), amount);
		}
		return cost;
	}

	// HWP: list label with the payer when more than one player is around
	string HWPBuffLabel(uint i)
	{
		auto buff = MissionBuff::Get(m_buffs[i]);
		string label = "- " + (buff is null ? "?" : Resources::GetString(buff.m_name));
		uint8 payer = i < m_payers.length() ? m_payers[i] : 0;
		if (HWP::Architect::ShowPayer())
			label += " (" + HWP::Architect::PayerName(payer) + ")";
		return label;
	}

	// HWP: the host's merged pick list
	void HWPSync(array<int>@ ids, array<int>@ payers)
	{
		int before = CalcMyCost().GetTotalCost();
		m_buffs.removeRange(0, m_buffs.length());
		m_payers.removeRange(0, m_payers.length());
		for (uint i = 0; i < ids.length(); i++)
		{
			m_buffs.insertLast(uint(ids[i]));
			m_payers.insertLast(uint8(i < payers.length() ? payers[i] : 0));
		}
		if (m_scroll !is null)
			Refresh();
		else if (m_menu !is null)
			m_menu.RefreshCost();

		// a share that changed under a readied player needs a fresh look (and a
		// fresh affordability check) before the host can start
		if (m_menu !is null && !Network::IsServer() && CalcMyCost().GetTotalCost() != before
			&& m_menu.GetLoadoutStatus() == MissionLoadoutStatus::Ready)
			m_menu.SetStatus(MissionLoadoutStatus::NotReady);
	}

	//bool UpdateTooltip(WindowManager@ manager) override
	//{
	//	for (uint i = 0; i < m_buttons.length(); i++)
	//	{
	//		if (m_buttons[i].m_hovering)
	//		{
	//			auto buff = MissionBuff::Get(m_buttons[i].m_id);
	//			if (buff !is null)
	//			{
	//				auto iconFrame = ScriptSprite(Resources::GetTexture2D("gui/gui.png"), vec4(76, 210, 28, 28));
	//				string desc = buff.m_description;
	//				if (buff.m_cost !is null)
	//					desc += "\n\n" + buff.m_cost.GetText(m_player);
					
	//				manager.SetTooltip(
	//					CreateTitledTooltip(Resources::GetSValue("gui/variable/itemtooltip_common.sval"),
	//						buff.m_name,
	//						desc,
	//						buff.m_icon,
	//						iconFrame)
	//				);
					
					
	//			}
				
	//			return true;
	//		}
	//	}
		
	//	return false;
	//}

	void NetSync(array<int>@ buffs)
	{
		// vanilla host-only sync; HWP keeps it working (all paid by the host)
		m_buffs.removeRange(0, m_buffs.length());
		m_payers.removeRange(0, m_payers.length());
		for (uint i = 0; i < buffs.length(); i++)
		{
			m_buffs.insertLast(int(buffs[i]));
			m_payers.insertLast(0);
		}

		m_menu.RefreshCost();
	}

	void OnFunc(Widget@ sender, const string &in name) override
	{
		print("MissionArchitect::" + name);
		
		auto parse = name.split(" ");
		if (parse[1] == "open")
		{
			cast<BaseGameMode>(g_gameMode).m_windowManager.AddWindowObject(
				SelectArchitectSelector(this));
		}
	}

}

class SelectArchitectSelector : AWindowObject
{
	SelectArchitectLoadout@ m_host;
	ITooltip@ m_selectedTooltip;
	Widget@ m_compareAnchor;

	array<uint> m_buffs;

	bool m_changed;
	Widget@ m_hwpPresets; // HWP: the preset row (gui/hwp_architect_presets.gui)

	SelectArchitectSelector(SelectArchitectLoadout@ host)
	{
		super(g_gameMode.m_guiBuilder, "gui/mission_loadout/architect_picker.gui");

		@m_host = host;

		@m_compareAnchor = m_widget.GetWidgetById("compare-anchor");

		auto templateW = m_widget.GetWidgetById("template");
		auto scroll = m_widget.GetWidgetById("scroll");

		auto buffs = MissionBuff::GetMissionBuffs(host.m_player, m_host.m_buffSet);
		bool challenges = HWP::Architect::Enabled(); // HWP: no challenges with the module off
		int row = 0;
		for (uint i = 0; i < buffs.length(); i++)
		{
			if (!challenges && HWP::Architect::ChallengeIndex(buffs[i].m_idHash) >= 0)
				continue;
			auto buffW = cast<AInteractableWidget>(templateW.Clone());
			buffW.m_visible = true;
			buffW.SetID(buffs[i].m_id);
			buffW.m_navPos = ivec2(0, row++);
			
			auto text = cast<TextWidget>(buffW.GetWidgetById("text"));
			text.SetText(Resources::GetString(buffs[i].m_name));
			
			auto cost = cast<TextWidget>(buffW.GetWidgetById("cost"));
			cost.m_textWidth = 55;
			// HWP: a challenge shows what it takes off, in red
			string off = HWP::Architect::DiscountText(buffs[i].m_idHash);
			if (off != "")
				cost.m_textWidth = 80; // two negative amounts wrap in 55
			cost.SetText(off != "" ? off : buffs[i].m_cost.GetText(host.m_player));

			HWPMarkWidget(buffW, buffs[i].m_idHash, Resources::GetString(buffs[i].m_name)); // HWP

			scroll.AddChild(buffW);
		}

		for (uint i = 0; i < m_host.m_buffs.length(); i++)
			m_buffs.insertLast(m_host.m_buffs[i]);

		if (HWP::Architect::Enabled())
			HWPBuildPresets(); // HWP

		RefreshCost();

		if (m_host.m_buffs.length() > 0)
			UpdateSelectedTooltip();

		@m_input.m_menuAdditionalOnPressed = WindowInput::OnFunc(this.Apply);
	}

	// HWP: the preset row under the list. The list's frame (the rect around "scroll")
	// gives up the row's height; the row is built from the module's own gui file and
	// registered with the window's input, so its buttons take clicks and key navigation.
	void HWPBuildPresets()
	{
		auto def = Resources::GetGUIDef("gui/hwp_architect_presets.gui");
		if (def is null)
		{
			HWP::LogError("architect", "gui/hwp_architect_presets.gui not found; no preset row");
			return;
		}
		auto row = cast<Widget>(m_builder.BuildGUI(def, this));
		if (row is null)
		{
			HWP::LogError("architect", "gui/hwp_architect_presets.gui failed to build; no preset row");
			return;
		}
		auto scroll = m_widget.GetWidgetById("scroll");
		if (scroll is null || scroll.m_parent is null || scroll.m_parent.m_parent is null)
			return;
		auto frame = scroll.m_parent;
		int shrink = row.m_height + 3;
		frame.m_height -= shrink;
		for (uint i = 0; i < frame.m_children.length(); i++)
			frame.m_children[i].m_height -= shrink;
		row.m_anchor = vec2(0.0f, 0.0f);
		row.m_offset = vec2(frame.m_offset.x, frame.m_offset.y + float(frame.m_height) + 3.0f);
		frame.m_parent.AddChild(row);
		@m_hwpPresets = row;
		HWPRefreshPresets();
		RefreshInteractableWidgets(m_widget);
		Invalidate();
		HWP::Log("architect", "preset row added to the picker");
	}

	// HWP: the slot buttons show their preset's name
	void HWPRefreshPresets()
	{
		if (m_hwpPresets is null)
			return;
		for (int slot = 1; slot <= HWP::Architect::PRESETS; slot++)
		{
			auto text = cast<TextWidget>(m_hwpPresets.GetWidgetById("hwp-preset-name-" + slot));
			if (text is null)
				continue;
			string name = HWP::Architect::PresetName(slot);
			if (name == "")
				name = Resources::GetString(".hwp.architect.preset_empty");
			text.SetText(name);
		}
	}

	// HWP: "hwp-preset load <n>" / "hwp-preset save <n>" from the row's buttons,
	// "hwp-preset-name <n>" back from the name dialog (sender is its text input)
	void HWPPresetFunc(Widget@ sender, const string &in name)
	{
		auto parse = name.split(" ");
		if (parse.length() < 2)
			return;
		int slot = int(parseInt(parse[parse.length() - 1]));
		if (parse[0] == "hwp-preset-name")
		{
			auto textInput = cast<TextInputWidget>(sender);
			string typed = "";
			if (textInput !is null)
				typed = textInput.m_text.plain();
			// HWP: the dialog's text input locks the window manager's input while it has
			// focus (TextInputWidget.Update); an Accept that skips its Submit event (the
			// mouse on OK, a driven func) leaves the lock on and the next Back only clears it
			auto gm = cast<BaseGameMode>(g_gameMode);
			if (gm !is null && gm.m_windowManager !is null)
				gm.m_windowManager.LockInput(false);
			int ngp = -1;
			if (m_host.m_menu !is null && m_host.m_menu.m_ngp)
				ngp = int(g_ngp + 0.5f);
			HWP::Architect::SavePreset(slot, typed, HWP::Architect::MyPicks(), ngp);
			HWPRefreshPresets();
			HWP::Commands::Reply(Resources::GetString(".hwp.architect.preset_saved", {{ "name", HWP::Architect::PresetName(slot) }}));
		}
		else if (parse[1] == "save")
		{
			string current = HWP::Architect::PresetName(slot);
			g_gameMode.ShowInputDialog("hwp-preset-name " + slot, Resources::GetString(".hwp.architect.preset_prompt"), this, current);
		}
		else if (parse[1] == "load")
		{
			if (HWP::Architect::ApplyPreset(slot, m_host.m_player, m_host.m_buffSet))
			{
				m_changed = true;
				HWP::Commands::Reply(Resources::GetString(".hwp.architect.preset_loaded", {{ "name", HWP::Architect::PresetName(slot) }}));
			}
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

	// HWP: checkmark + "(payer)" suffix for one row of the picker
	void HWPMarkWidget(Widget@ buffW, uint id, const string &in baseName)
	{
		int idx = m_host.m_buffs.find(id);
		buffW.GetWidgetById("selected").m_visible = idx > -1;
		auto text = cast<TextWidget>(buffW.GetWidgetById("text"));
		if (text is null)
			return;
		string label = baseName;
		if (idx > -1)
		{
			uint8 payer = uint(idx) < m_host.m_payers.length() ? m_host.m_payers[idx] : 0;
			if (HWP::Architect::ShowPayer())
				label += " (" + HWP::Architect::PayerName(payer) + ")";
		}
		text.SetText(label);
	}

	// HWP: the host sent a new merged list while the picker is open
	void RefreshFromHost()
	{
		auto buffs = MissionBuff::GetMissionBuffs(m_host.m_player, m_host.m_buffSet);
		auto list = m_widget.GetWidgetById("scroll");
		for (uint i = 0; i < list.m_children.length(); i++)
		{
			auto child = list.m_children[i];
			string baseName;
			for (uint j = 0; j < buffs.length(); j++)
				if (buffs[j].m_idHash == child.m_idHash)
					baseName = Resources::GetString(buffs[j].m_name);
			HWPMarkWidget(child, child.m_idHash, baseName);
		}

		m_buffs.removeRange(0, m_buffs.length());
		for (uint i = 0; i < m_host.m_buffs.length(); i++)
			m_buffs.insertLast(m_host.m_buffs[i]);

		RefreshCost();
		UpdateSelectedTooltip();
	}

	void RefreshCost()
	{
		auto cost = cast<TextWidget>(m_widget.GetWidgetById("total-cost"));
		cost.SetText(m_host.CalcMyCost().GetText(m_host.m_player)); // HWP: your share
		
		
		float mul = HWP::Architect::CostMul(m_buffs); // HWP: challenges discount
		auto costMul = cast<TextWidget>(m_widget.GetWidgetById("cost-mul"));
		costMul.SetText(Resources::GetString(".architect.cost_mul", {{ "mul", int(mul * 100.0f + 0.5f) + "%" }}));
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

	void UpdateSelectedTooltip()
	{
	
		string title = Resources::GetString(".menu.loadout.alterations");
		string description;

		for (uint i = 0; i < m_buffs.length(); i++)
		{
			auto missionBuff = MissionBuff::Get(m_buffs[i]);
			if (missionBuff is null)
				continue;
			
			description += "- " + Resources::GetString(missionBuff.m_description);
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

	void Apply()
	{
		// HWP: picks are live-synced from the host; applying just closes
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

		return true;
	}

	void OnFunc(Widget@ sender, const string &in name) override
	{
		if (name.findFirst("hwp-preset") == 0) // HWP: the preset row and its name dialog
		{
			HWPPresetFunc(sender, name);
			return;
		}
		if (name == "hover")
		{
			auto buff = MissionBuff::Get(sender.m_idHash);
			if (buff !is null)
			{
				string desc = Resources::GetString(buff.m_description);
				if (buff.m_cost !is null)
					desc += "\n\n" + buff.m_cost.GetText(m_host.m_player);
				
				m_manager.SetTooltip(
					CreateTitledTooltip(Resources::GetSValue("gui/variable/itemtooltip_common.sval"),
						Resources::GetString(buff.m_name),
						desc,
						null,
						null)
				, true);
			}
		}
		else if (name == "select")
		{
			// HWP: toggle my own pick; the host merges everyone's picks and
			// syncs the list back (architect.sync -> RefreshFromHost)
			uint id = sender.m_idHash;
			uint8 me = uint8(Lobby::GetLocalPeer());
			int idx = m_host.m_buffs.find(id);
			if (idx > -1 && uint(idx) < m_host.m_payers.length() && m_host.m_payers[idx] != me)
				return; // someone else's pick, only they can remove it

			array<int> mine;
			for (uint i = 0; i < m_host.m_buffs.length(); i++)
			{
				if (i < m_host.m_payers.length() && m_host.m_payers[i] == me && m_host.m_buffs[i] != id)
					mine.insertLast(int(m_host.m_buffs[i]));
			}
			if (idx < 0)
				mine.insertLast(int(id));

			HWP::Architect::SendPicks(mine);
			HWP::Architect::RememberPicks(mine); // HWP: the last picks come back next time
			m_changed = true;
		}
		else if (name == "exit yes")
			Apply();
		else if (name == "exit no")
			m_closing = true;
	}
}

class ToppleTowersTask : QueuedTasks::QueuedTask
{
	ToppleTowersTask() { }
	ToppleTowersTask(SValue@ save) { }
	
	void Execute() override
	{
		if (!Network::IsServer())
			return;
		
		uint towerTag = 1 << g_actorTags.GetTag("tower");
		auto enemies = g_scene.FetchAllActorsWithOtherTeam(g_team_player);
		int numDestroyed = 0;
		
		print("Architect: Toppling towers, tag: " + towerTag);
		for (uint i = 0; i < enemies.length(); i++)
		{
			auto actor = cast<Actor>(enemies[i].GetScriptBehavior());
			if ((actor.Tags & towerTag) == towerTag)
			{
				actor.Kill(null, 0);
				numDestroyed++;
			}
		}
		print("Toppled " + numDestroyed + " towers");
	}
}

class RevealWaygatesTask : QueuedTasks::QueuedTask
{
	RevealWaygatesTask() { }
	RevealWaygatesTask(SValue@ save) { }
	
	void Execute() override
	{
		//if (!Network::IsServer())
		//	return;
		
		auto allBeacons = g_scene.FetchAllUnitsWithBehavior("TeleportBeacon");
		for (uint i = 0; i < allBeacons.length(); i++)
		{
			auto beacon = cast<TeleportBeacon>(allBeacons[i].GetScriptBehavior());
			if (beacon !is null)
				beacon.Reveal();
		}
		
		print("Revealed " + allBeacons.length() + " waygates");
	}
}