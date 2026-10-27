// HWP override of scripts/GUI/MissionLoadoutMenu.as (see mods/architect/README.md,
// "Run-start screen"). Every change is marked HWP; pristine copy: MissionLoadoutMenu.as.orig
class MissionLoadout : SVO
{
	int m_width;
	int m_height;
	string m_name;
	
	ConditionalList@ m_conditionals;
	
	MissionLoadout(SValue& params)
	{
		UnitPtr u;
		
		m_width = GetParamInt(u, params, "width", true);
		m_height = GetParamInt(u, params, "height", true);
		m_name = GetParamString(u, params, "name", true);
		
		@m_conditionals = LoadConditionals(u, params);
	}
	
	bool BuildGUI(PlayerRecord@ plr, MissionLoadoutMenu@ menu, Widget@ segment, int yNavPos) { return true; }
	bool UpdateTooltip(WindowManager@ manager) { return false; }
	void OnPlay() {}
	void OnFunc(Widget@ sender, const string &in name) {}
	ShopCost@ GetCost() { return null; }
	
	void Save(SValueBuilder& builder) {}
	void Load(PlayerRecord@ plr, SValue@ save) {}
}

class MissionGUILoadout : MissionLoadout
{
	string m_guiFile;
	MissionLoadoutMenu@ m_menu;
	
	MissionGUILoadout(SValue& params)
	{
		super(params);
		
		UnitPtr u;
		
		m_guiFile = GetParamString(u, params, "gui", true);
	}
	
	bool BuildGUI(PlayerRecord@ plr, MissionLoadoutMenu@ menu, Widget@ segment, int yNavPos) override
	{
		GUIDef@ guiDef = Resources::GetGUIDef(m_guiFile);
		if (guiDef is null)
		{
			PrintError("MissionLoadout GUI Definition is null: '" + m_guiFile + "'");
			return false;
		}
		
		auto widget = cast<Widget>(menu.m_builder.BuildGUI(guiDef, menu));
		if (widget is null)
		{
			PrintError("MissionLoadout GUI build failed for: '" + m_guiFile + "'");
			return false;
		}
		
		@m_menu = menu;
		segment.AddChild(widget);
		return true;
	}
}

enum MissionLoadoutStatus
{
	None,
	NotReady,
	Ready,
	Started
}

interface IMissionLoadoutMenuStartCallback
{
	void OnStart();
	void OnUpdate(int ms);
}

class MissionLoadoutMenu : AWindowObject
{
	Widget@ m_outerWindow;
	Widget@ m_contentWindow;
	
	Widget@ m_segmentTemplate;
	Widget@ m_bridgeTemplate;

	Widget@ m_ngpW;
	bool m_ngp;

	array<MissionLoadout@> m_loadouts;

	TextWidget@ m_readyCountW;
	TextWidget@ m_readyTextW;
	TextWidget@ m_costW;

	ShopCost@ m_totCost;
	bool m_canAfford;

	bool m_allReady;

	IMissionLoadoutMenuStartCallback@ m_startClbk;
	IMissionSpec@ m_missionSpec;

	array<Widget@> m_hwpBridges; // HWP: the decorative bridges, dropped when the window would not fit the screen
	bool m_hwpTopAligned;        // HWP: the window moved to the top edge so the key hints below it stay on screen


	MissionLoadoutMenu(GUIBuilder@ b, IMissionLoadoutMenuStartCallback@ startClbk = null, IMissionSpec@ missionSpec = null)
	{
		super(b, "gui/mission_loadout.gui");
		
		@m_missionSpec = missionSpec;
		@m_startClbk = startClbk;
		
		if (Network::IsServer())
		{
			auto missionDef = MissionManager::GetCurrentMission();
			if (missionDef !is null && missionDef.m_levels.length() > 0 && missionDef.m_setHash != HashString("heaven"))
				MissionManager::PreloadNextLevel(missionDef.m_levels[0].m_id);
			
			(Network::Message("OpenMissionLoadoutMenu") << MissionManager::g_module.m_missionDefHash << MissionManager::g_module.m_missionRewardSeed).SendToAll();
			
			if (m_missionSpec is null || m_missionSpec.ConfigurableNGP())
				m_ngp = GetLocalPlayerRecord().ngp > 0;
		}
		
		@m_totCost = ShopCost();
		@m_segmentTemplate = m_widget.GetWidgetById("template-segment");
		@m_bridgeTemplate = m_widget.GetWidgetById("template-bridge");
		
		@m_outerWindow = m_widget.GetWidgetById("window");
		@m_contentWindow = m_widget.GetWidgetById("content");
		
		@m_readyCountW = cast<TextWidget>(m_widget.GetWidgetById("ready_text"));
		@m_readyTextW = cast<TextWidget>(m_widget.GetWidgetById("waiting_for_text"));
		@m_costW = cast<TextWidget>(m_widget.GetWidgetById("cost"));
		
		
		auto titleW = cast<TextWidget>(m_widget.GetWidgetById("title"));
		string missionName = "";
		
		if (missionName.isEmpty() && m_missionSpec !is null)
			missionName = m_missionSpec.GetLoadoutTitle();
		
		if (missionName.isEmpty())
		{
			auto currMissionDef = MissionDef::Get(MissionManager::g_module.m_missionDefHash);
			if (currMissionDef !is null)
				missionName = Resources::GetString(".menu.loadout.starting_mission", {{ "mission", currMissionDef.m_name }});
		}
		
		titleW.SetText(missionName);
		
		if (m_ngp)
		{
			@m_ngpW = m_widget.GetWidgetById("ngp").Clone();
			m_ngpW.m_visible = true;
			// HWP: the row goes in after the loadout segments, right above the Start line,
			// and the level the host picked last time comes back (architect.ngp)
			m_outerWindow.m_height += m_ngpW.m_height + m_contentWindow.m_spacing;
			int lastNgp = HWP::Architect::LastNGP();
			if (lastNgp >= 0 && HWP::Architect::Enabled())
				g_ngp = float(min(int(GetLocalPlayerRecord().ngp), lastNgp));
		}

		RefreshNGP();
		
		auto plr = GetLocalPlayerRecord();
		m_widget.GetWidgetById("pot-warning").m_visible = g_flags.IsSet("mission_story_intro_find_npcs") && plr.currStats.PotionCharges <= 0;
		
		for (uint i = 0; i < MissionLoadout::Instances.length(); i++)
		{
			auto loadout = MissionLoadout::Instances[i];
			
			if (!CheckConditionals(loadout.m_conditionals, plr))
				continue;
			
			auto seg = m_segmentTemplate.Clone();
			cast<TextWidget>(seg.GetWidgetById("name")).SetText(Resources::GetString(loadout.m_name));
			seg.m_visible = true;
			
			if (!loadout.BuildGUI(plr, this, seg, i))
				continue;
			
			seg.m_height += loadout.m_height;
			m_outerWindow.m_height += loadout.m_height + m_contentWindow.m_spacing;
			//m_contentWindow.m_height += loadout.m_height;
			seg.GetWidgetById("container").m_height = seg.m_height;

			m_contentWindow.AddChild(seg);
			m_loadouts.insertLast(loadout);

			if (i != MissionLoadout::Instances.length() - 1)
			{
				auto bridge = m_bridgeTemplate.Clone();
				bridge.m_visible = true;

				m_outerWindow.m_height += bridge.m_height;
				m_contentWindow.m_height += bridge.m_height;

				m_contentWindow.AddChild(bridge);
				m_hwpBridges.insertLast(bridge); // HWP
			}
		}

		// HWP: the New Game+ row sits under the options, next to Start
		if (m_ngpW !is null)
			m_contentWindow.AddChild(m_ngpW);
		HWPFitToScreen();

		@m_input.m_menuAdditionalOnPressed = WindowInput::OnFunc(this.Play);
		
		RefreshInteractableWidgets(m_widget);
		
		SetStatus(MissionLoadoutStatus::NotReady);
		RefreshCost();
		
		
		plr.ResetForNewMission();
		plr.RefreshModifiers();
		g_flags.ClearFlags(FlagState::Run);
	}

	void RefreshCost()
	{
		@m_totCost = ShopCost();
		
		for (uint i = 0; i < m_loadouts.length(); i++)
		{
			auto cost = m_loadouts[i].GetCost();
			if (cost is null)
				continue;
			m_totCost.AddCost(cost);
		}
		
		m_costW.SetText(m_totCost.GetText(GetLocalPlayerRecord()));
		
		auto input = GetInput();
		if (input !is null)
			RefreshKeybinds(input.GetCurrentMap());
		else
			RefreshKeybinds(null);
	}

	void RefreshReadyTexts()
	{
		string waitingFor = "";
		int readyCount = 0;
		int notReadyCount = 0;
		int totalCount = 0;
		
		for (uint i = 0; i < g_players.length(); i++)
		{
			auto player = g_players[i];
			if (player.peer == 255)
				continue;
			
			int loadoutStatus = int(MissionLoadoutStatus::None);
			if (!player.userdata.get("loadout_status", loadoutStatus))
				continue;
			
			if (loadoutStatus == int(MissionLoadoutStatus::None))
				continue;
			
			totalCount++;
			if (player.peer == 0)
				readyCount++;
			else if (loadoutStatus == int(MissionLoadoutStatus::Ready))
				readyCount++;
			else
			{
				notReadyCount++;
				if (waitingFor.isEmpty())
					waitingFor = player.GetName();
				else
					waitingFor += ", " + player.GetName();
			}
		}
		
		if (totalCount <= 1)
		{
			m_allReady = true;
			m_readyCountW.SetText("");
			m_readyTextW.SetText("");
		}
		else
		{
			m_allReady = false;
			m_readyCountW.SetText(Resources::GetString(".menu.loadout.numready", {{ "ready", readyCount }, { "total", totalCount }}));
			if (waitingFor <= 0)
			{
				m_allReady = true;
				m_readyTextW.SetText("");
			}
			else if (waitingFor.length() > 20)
				m_readyTextW.SetText(Resources::GetString(".menu.loadout.waiting_num", {{ "num", notReadyCount }}));
			else
				m_readyTextW.SetText(Resources::GetString(".menu.loadout.waiting_plrs", {{ "players", waitingFor }}));
		}
		
		auto input = GetInput();
		if (input !is null)
			RefreshKeybinds(input.GetCurrentMap());
		else
			RefreshKeybinds(null);
	}

	void RefreshKeybinds(ControlMap@ currMap) override
	{
		if (m_navigationBar is null)
			return;
		
		auto loadoutStatus = GetLoadoutStatus();
		array<KeyNavigationText@> navTexts;

		if (loadoutStatus != MissionLoadoutStatus::Started)
		{
			navTexts.insertLast(KeyNavigationText(m_navigationBar.m_font.BuildText(FormatKeyName(GetActionBinding("MenuForward")) + " " + Resources::GetString(".menu.nav.select"))));

			string playName = "";
			if (Network::IsServer())
				playName = "start";
			else if (loadoutStatus == MissionLoadoutStatus::Ready)
				playName = "unready";
			else //if (loadoutStatus == MissionLoadoutStatus::NotReady)
				playName = "ready";
			
			m_canAfford = m_totCost.CanAfford(GetLocalPlayerRecord());
			if (!m_canAfford)
				playName = "";
			
			// HWP: the host's Start hint says which New Game+ level the run begins on
			string playText = Resources::GetString(".menu.nav." + playName);
			if (playName == "start" && m_ngp)
				playText = Resources::GetString(".hwp.architect.start_ngp", {{ "ngp", int(g_ngp + 0.5f) }});
			if (m_canAfford && !playName.isEmpty())
				navTexts.insertLast(KeyNavigationText(m_navigationBar.m_font.BuildText(FormatKeyName(GetActionBinding("MenuAdditional")) + " " + playText), WindowInput::OnFunc(this.Play)));

			if (m_ngp)
			{
				navTexts.insertLast(KeyNavigationText(m_navigationBar.m_font.BuildText(FormatKeyName(GetActionBinding("MenuPreviousSubTab")) + " " + Resources::GetString(".menu.nav.ngp-")), WindowInput::OnFunc(this.DecreaseNGP)));
				navTexts.insertLast(KeyNavigationText(m_navigationBar.m_font.BuildText(FormatKeyName(GetActionBinding("MenuNextSubTab")) + " " + Resources::GetString(".menu.nav.ngp+")), WindowInput::OnFunc(this.IncreaseNGP)));
			}
		}
		
		m_navigationBar.BuildBar(navTexts, this);
	}

	void RefreshNGP()
	{
		if (m_missionSpec !is null && !m_missionSpec.ConfigurableNGP())
		{
			g_ngp = m_missionSpec.GetNGP();
		}
		else
		{
			g_ngp = min(GetLocalPlayerRecord().ngp, int(g_ngp + 0.5f));
		}
		
		print("RefreshNGP " + g_ngp);
		if (m_ngpW !is null)
		{
			// HWP: "Starting on New Game+ N" (the base game at 0), and the Start hint follows
			int ngp = int(g_ngp + 0.5f);
			string rowKey = ".hwp.architect.ngp_row0";
			if (ngp > 0)
				rowKey = ".hwp.architect.ngp_row";
			cast<TextWidget>(m_ngpW.GetWidgetById("ngp-text")).SetText(Resources::GetString(rowKey, {{"ngp", ngp}}));
			auto input = GetInput();
			if (input !is null)
				RefreshKeybinds(input.GetCurrentMap());
			else
				RefreshKeybinds(null);
		}
	}

	// HWP: a preset's level (host only, as the arrows); clamped to the character's own
	void HWPSetNGP(int ngp)
	{
		if (!m_ngp)
			return;
		g_ngp = float(clamp(ngp, 0, int(GetLocalPlayerRecord().ngp)));
		RefreshNGP();
		HWP::Architect::RememberNGP(int(g_ngp + 0.5f));
	}

	// HWP: the window is centred and its key hints (KeyNavigationBar, 20 px of gui.png) are
	// drawn under it, so a tall loadout (every town building, farming's herb line, New
	// Game+) pushes Start and the hints off a 360-unit screen. First the decorative
	// bridges go, then the window moves to the top edge so the hints keep their 20 px.
	void HWPFitToScreen()
	{
		const int BAR = 20;
		const int MARGIN = 2;
		int screen = int(g_gameMode.m_wndHeight);
		bool dropped = false;
		if (m_outerWindow.m_height + 2 * (BAR + MARGIN) > screen && m_hwpBridges.length() > 0)
		{
			for (uint i = 0; i < m_hwpBridges.length(); i++)
			{
				m_outerWindow.m_height -= m_hwpBridges[i].m_height;
				m_contentWindow.m_height -= m_hwpBridges[i].m_height;
				m_hwpBridges[i].RemoveFromParent();
			}
			m_hwpBridges.removeRange(0, m_hwpBridges.length());
			dropped = true;
		}
		if ((screen - m_outerWindow.m_height) / 2 < BAR + MARGIN)
		{
			m_outerWindow.m_anchor = vec2(0.5f, 0.0f);
			m_outerWindow.m_offset = vec2(0.0f, float(MARGIN));
			m_hwpTopAligned = true;
		}
		Invalidate();
		string layout = ", centred";
		if (m_hwpTopAligned)
			layout = ", top-aligned";
		HWP::Log("architect", "run-start layout: window " + m_outerWindow.m_height + " of " + screen + " px"
			+ (dropped ? ", bridges dropped" : "") + layout
			+ (m_ngpW !is null ? ", NG+ row" : ""));
	}

	void IncreaseNGP()
	{
		auto maxNgp = int(GetLocalPlayerRecord().ngp);
		if (int(g_ngp + 0.5f) >= maxNgp - 0.5f)
			g_ngp = 0.0f;
		else
			g_ngp = float(min(maxNgp, int(g_ngp + 0.5f) + 1));

		RefreshNGP();
		HWP::Architect::RememberNGP(int(g_ngp + 0.5f)); // HWP
	}

	void DecreaseNGP()
	{
		if (g_ngp <= 0.5f)
			g_ngp = float(GetLocalPlayerRecord().ngp);
		else
			g_ngp = float(max(0, int(g_ngp + 0.5f) - 1));

		RefreshNGP();
		HWP::Architect::RememberNGP(int(g_ngp + 0.5f)); // HWP
	}

	void Play() 
	{ 
		if (!m_canAfford)
			return;

		OnFunc(null, "play"); 
	}

	bool Back() override
	{
		SetStatus(MissionLoadoutStatus::None);
		if (Network::IsServer())
		{
			(Network::Message("CloseMissionLoadoutMenu")).SendToAll();
			HWP::Log("architect", "run-start setup closed by the host"); // HWP
			return true;
		}

		if (!HWP::Architect::Enabled()) // HWP: the module off: vanilla, the client stays
			return false;

		// HWP: vanilla returned false here, which kept a client in the window until the
		// host started or closed it. Now the client's own window closes (its status is
		// None, so the host's ready count and start skip it) and the mission board opens
		// it again while the host's setup is still up (MissionShopContent override).
		HWP::Log("architect", "run-start setup left by a client (rejoin at the mission board)");
		HWP::Commands::Reply(Resources::GetString(".hwp.architect.client_left"));
		return true;
	}

	void OnInteractableIndexChanged() override 
	{
		if (m_manager is null)
			return;
		
		m_manager.CloseTooltip();
		for (uint i = 0; i < m_loadouts.length(); i++)
		{
			if (m_loadouts[i].UpdateTooltip(m_manager))
				break;
		}
	}

	void SetStatus(MissionLoadoutStatus status)
	{
		(Network::Message("SetMissionLoadoutStatus") << int(status)).SendToAll();
		
		auto plr = GetLocalPlayerRecord();
		if (plr.peer == 0 && status == MissionLoadoutStatus::Ready) // HWP
			HWP::Log("architect", "host starts the run at NG+ " + int(g_ngp + 0.5f));
		NetSetStatus(plr, status);

		if (plr.peer == 0 && status == MissionLoadoutStatus::Ready)
			SetStatus(MissionLoadoutStatus::Started);
	}

	void NetSetStatus(PlayerRecord@ plr, MissionLoadoutStatus status)
	{
		if (plr.peer == 0 && status == MissionLoadoutStatus::Started)
		{
			if (GetLoadoutStatus(plr) != status)
			{
				for (uint i = 0; i < m_loadouts.length(); i++)
					m_loadouts[i].OnPlay();
			}
			
			if (m_startClbk !is null)
				m_startClbk.OnStart();
			
			if (!plr.local)
				SetStatus(MissionLoadoutStatus::Started);
		}
		
		plr.userdata.set("loadout_status", int(status));
		RefreshReadyTexts();
		
		CheckToStart();
	}

	void CheckToStart()
	{
		if (!Network::IsServer())
			return;
		
		for (uint i = 0; i < g_players.length(); i++)
		{
			auto player = g_players[i];
			if (player.peer == 255)
				continue;
			
			auto loadoutStatus = GetLoadoutStatus(player);
			if (player.peer != 0 && loadoutStatus == MissionLoadoutStatus::None)
				continue;
			
			if (loadoutStatus == MissionLoadoutStatus::Started)
				continue;
			
			return;
		}
		
		MissionManager::g_module.StartMission();
	}

	MissionLoadoutStatus GetLoadoutStatus()
	{
		int loadoutStatus = int(MissionLoadoutStatus::None);
		GetLocalPlayerRecord().userdata.get("loadout_status", loadoutStatus);
		return MissionLoadoutStatus(loadoutStatus);
	}

	MissionLoadoutStatus GetLoadoutStatus(PlayerRecord@ plr)
	{
		int loadoutStatus = int(MissionLoadoutStatus::None);
		plr.userdata.get("loadout_status", loadoutStatus);
		return MissionLoadoutStatus(loadoutStatus);
	}

	bool Update(int ms, GameInput& gameInput, MenuInput& menuInput) override
	{
%if GAME
		if (m_ngp)
		{
			if (menuInput.MenuPreviousSubTab.Pressed)
				DecreaseNGP();
			if (menuInput.MenuNextSubTab.Pressed)
				IncreaseNGP();
		}
%endif

		if (m_startClbk !is null)
			m_startClbk.OnUpdate(ms);

		return AWindowObject::Update(ms, gameInput, menuInput);
	}

	void OnFunc(Widget@ sender, const string &in name) override
	{
		print(name);

		auto loadoutStatus = GetLoadoutStatus();
		
		if (loadoutStatus == MissionLoadoutStatus::Started)
			return;

		if (name == "ngminus" && m_ngp)
		{
			DecreaseNGP();
			return;
		}
		else if (name == "ngplus" && m_ngp)
		{
			IncreaseNGP();
			return;
		}

		if (name == "force yes" || name == "hwpngp yes") // HWP: the NG+ confirmation
		{
			SetStatus(MissionLoadoutStatus::Ready);
			return;
		}

		auto parse = name.split(" ");
		if (parse[0] == "play")
		{
			if (loadoutStatus == MissionLoadoutStatus::Ready)
				SetStatus(MissionLoadoutStatus::NotReady);
			else
			{
				// HWP: the host confirms the New Game+ level it starts on (architect.confirm_ngp,
				// default on); the force-start question carries it too
				int ngp = int(g_ngp + 0.5f);
				bool confirmNgp = m_ngp && ngp > 0 && HWP::Architect::Enabled() && HWP::Settings::GetBool("architect.confirm_ngp", true);
				if (Network::IsServer() && !m_allReady)
				{
					string warning = Resources::GetString(".menu.loadout.force_start_warning");
					if (m_ngp)
						warning += "\n\n" + Resources::GetString(".hwp.architect.confirm_ngp", {{ "ngp", ngp }});
					g_gameMode.ShowDialog("force", warning, Resources::GetString(".menu.yes"), Resources::GetString(".menu.no"), this);
				}
				else if (Network::IsServer() && confirmNgp)
					g_gameMode.ShowDialog("hwpngp", Resources::GetString(".hwp.architect.confirm_ngp", {{ "ngp", ngp }}), Resources::GetString(".menu.yes"), Resources::GetString(".menu.no"), this);
				else
					SetStatus(MissionLoadoutStatus::Ready);
			}
		}
		else
		{
			auto loadout = MissionLoadout::Get(parse[0]);
			if (loadout !is null)
				loadout.OnFunc(sender, name);
		}
	}
}

class MissionMapFromClientLoadoutStarter : IMissionLoadoutMenuStartCallback, IWidgetHoster, IMissionSpec
{
	PlayerRecord@ m_sender;
	MissionDef@ m_mission;
	Item::Quality m_rewardEqQuality;
	Equipment::Slot m_rewardEqSlot;
	int m_rewardILvl;

	MissionMapFromClientLoadoutStarter(PlayerRecord@ sender, MissionDef@ mission, Item::Quality rewardEqQuality, Equipment::Slot rewardEqSlot, int rewardILvl)
	{
		@m_sender = sender;
		@m_mission = mission;
		m_rewardEqQuality = rewardEqQuality;
		m_rewardEqSlot = rewardEqSlot;
		m_rewardILvl = rewardILvl;
	}

	void OnStart()
	{
		// Remove map from m_sender
		(Network::Message("HostStartingMap") << m_mission.m_idHash << int(m_rewardEqQuality) << int(m_rewardEqSlot) << m_rewardILvl).SendToPeer(m_sender.peer);
	}

	void OnUpdate(int ms)
	{
		// If m_sender is not connected, close MissionLoadoutMenu
		if (m_sender.peer == 255)
		{
			auto gm = cast<BaseGameMode>(g_gameMode);
			for (uint i = 0; i < gm.m_windowManager.m_objects.length(); i++)
			{
				auto missionLoadoutWindow = cast<MissionLoadoutMenu>(gm.m_windowManager.m_objects[i]);
				if (missionLoadoutWindow is null)
					continue;
				
				gm.m_windowManager.CloseWindow(missionLoadoutWindow);
				return;
			}
		}
	}

	void OnFunc(Widget@ sender, const string &in name) override
	{
		if (name == "a yes")
		{
			MissionManager::SetMission(m_mission.m_idHash, randi(), m_rewardEqSlot, m_rewardILvl);
			
			auto gm = cast<BaseGameMode>(g_gameMode);
			gm.m_windowManager.AddWindowObject(MissionLoadoutMenu(gm.m_guiBuilder, this, this));
		}
	}

	bool ConfigurableNGP() { return false; }
	float GetNGP()
	{
		if(m_mission.m_setHash == HashString("heaven"))
			return m_rewardILvl;
		else
			return (m_rewardILvl - m_mission.m_baseDiffLevel) / float(Tweak::LevelCapNGPAdd);
	}
	
	string GetLoadoutTitle()
	{
		auto ilvlStr = Resources::GetString(".tooltip.equipment.ilvl", {{"ilvl", m_rewardILvl}});
		return Resources::GetString(".menu.loadout.starting_mission_from", {
			{ "name", m_sender.GetName() },
			{ "mission", m_mission.m_name + "  (" + ilvlStr + ")" }
		});
	}
}