// Chat item links. The base game already has item linking: holding the context
// key for a second on an inventory item fires GameEvents::PlayerLinkedItem on
// every machine (Character.as -> "PlayerLinkedItem" message -> PlayerHandler),
// but only the short-lived loot log reacts. This module listens to the same
// event and writes a persistent line into the chat log, and adds
// "hwp link [slot]" to link an equipped item without opening the inventory.
// Issue #62: the hold was hard to find, and the chat line showed only the name.
// - Linking: a "Link in chat" hint on every bag item (hwplib ItemActions:
//   clickable, key L, rebindable on the Plus tab), and a right-click on any item
//   of the character tab, bag or equipped (PollRightClick: the mouse button the
//   game resolves "mouse_right" to, read raw while the tab is on top).
// - The chat line is "Player: [Item]", the item in its quality colour.
// - Hovering: the chat lives in the main menu's script context (MainMenuGameMode
//   .m_wChat), out of reach of gameplay scripts, so its lines can't be hovered.
//   Instead a HUD panel just above the chat (HWPChatLinksHUD) lists the last
//   links, each in its quality colour; the cursor on one puts the item's vanilla
//   tooltip up (picture, stats, description) through the window manager, as the
//   loot log does (MouseOverTooltip), beside the line. Remote links carry the whole item
//   (Item::SaveItem), so every machine shows the same tooltip. The panel stays
//   SHOW_MS after a link (longer while hovered); "hwp links" brings it back.
// Setting: chatlinks.enabled (per machine; off: no chat line, no panel, no hint,
// no right-click link, hwp link says so).
namespace HWP
{
	namespace ChatLinks
	{
		const int LINK_KEY_DEFAULT = 15; // SDL scancode for L ("link")
		const uint MAX_LINKS = 5;        // panel lines
		const int SHOW_MS = 30000;       // the panel's time up after a link

		bool Enabled() { return HWP::Settings::GetBool("chatlinks.enabled", true); }

		string Link(Item::Item@ item)
		{
			return "\\c" + Item::QualityColorString(item.GetQuality()) + "[" + item.GetName() + "]\\d";
		}

		// a link on the panel
		class Linked
		{
			Item::Item@ m_item;
			ITooltip@ m_tip;
		}

		array<Linked@> g_links;
		HWPChatLinksHUD@ g_hud;
		// counters for `hwp chatlinks`
		int g_announced = 0, g_tips = 0, g_byAction = 0, g_byRight = 0;
		string g_last = "";

		void Announce(PlayerRecord@ plr, Item::Item@ item)
		{
			SValueBuilder b;
			b.PushString("\\c" + GetPlayerColor(plr.peer) + plr.GetName() + "\\d: " + Link(item));
			SendSystemMessage("AddChat", b.Build());
			g_announced++;
			Linked l;
			@l.m_item = item;
			g_links.insertLast(l);
			while (g_links.length() > MAX_LINKS)
				g_links.removeAt(0);
			if (g_hud !is null)
				g_hud.Show();
			HWP::Log("chatlinks", "chat line: " + plr.GetName() + " linked " + item.GetName() + " (" + g_links.length() + " on the panel)");
		}

		int SlotFromName(const string &in name)
		{
			if (name == "off") return int(EquippedItemsSlots::OffHand);
			if (name == "head") return int(EquippedItemsSlots::Head);
			if (name == "chest") return int(EquippedItemsSlots::Chest);
			if (name == "feet") return int(EquippedItemsSlots::Feet);
			if (name == "hands") return int(EquippedItemsSlots::Hands);
			if (name == "back") return int(EquippedItemsSlots::Back);
			return int(EquippedItemsSlots::MainHand);
		}

		// Same two calls Character.as makes when the context key is held.
		void LinkItem(PlayerRecord@ plr, Item::Item@ item)
		{
			GameEvents::PlayerLinkedItem(plr, item);
			SValueBuilder builder;
			Item::SaveItem(builder, item);
			(Network::Message("PlayerLinkedItem") << builder.Build()).SendToAll();
		}

		// --- linking from the inventory -------------------------------------------------------

		// "Link in chat" on a bag item (hint, click, key)
		class LinkAction : HWP::ItemActions::KeyedAction
		{
			LinkAction() { super("chatlinks.key", LINK_KEY_DEFAULT); }

			string Id() override { return "link"; }
			int Order() override { return 40; }

			string Label(Equipment::Equipment@ item) override
			{
				return Enabled() ? Resources::GetString(".hwp.chatlinks.action") : "";
			}

			void Do(PlayerRecord@ record, Equipment::Equipment@ item) override
			{
				g_byAction++;
				g_last = "action: " + item.GetName();
				HWP::Log("chatlinks", "linked by the action: " + item.GetName());
				LinkItem(record, item);
			}
		}

		// the character tab's item under the cursor (or the selection): a bag item or an
		// equipped one
		Item::Item@ HoveredItem()
		{
			auto tab = HWP::ItemActions::g_tab;
			if (tab is null)
				return null;
			auto bag = tab.HWPHoveredItem();
			if (bag !is null)
				return bag.m_item;
			auto worn = cast<EquipmentItemWidget>(tab.m_input.GetCurrentInteractable());
			if (worn is null || worn.m_item is null || worn.m_type != ItemWidgetType::Equipped)
				return null;
			return worn.m_item;
		}

		string HoveredItemName()
		{
			auto item = HoveredItem();
			return item is null ? "none" : item.GetName();
		}

		// right-click: link the hovered item; "" when it did (the reason it didn't otherwise)
		string LinkHovered(const string &in how)
		{
			if (!Enabled())
				return "off";
			if (!HWP::ItemActions::TabOpen())
				return "the character tab is not on top";
			auto item = HoveredItem();
			auto plr = GetLocalPlayerRecord();
			if (item is null || plr is null)
				return "no item under the cursor";
			g_byRight++;
			g_last = how + ": " + item.GetName();
			HWP::Log("chatlinks", "linked by " + how + ": " + item.GetName());
			LinkItem(plr, item);
			return "";
		}

		int g_rightButton = -1;
		bool g_rightDown = false;
		// `hwp chatlinks rclick` (a test's stand-in for the button, which GameLab's lab mode
		// can't press): one press, taken on the first frame within 3 s the tab is on top
		// again (the console the line was typed into has the keyboard until then)
		int g_fakeRight = 0;

		// the right mouse button, read raw (the menu binds nothing to it; in play it is the
		// off-hand attack, so this only acts while the character tab is on top)
		void PollRightClick(int ms)
		{
			if (g_rightButton < 0)
			{
				ControllerType type;
				int key = Platform::ResolveInputKey("mouse_right", type);
				// SDL_BUTTON_RIGHT, 3 (the kbm map's mouse_right binding reads key 3, type Mouse)
				g_rightButton = type == ControllerType::Mouse && key > 0 ? key : 3;
			}
			bool down = Platform::IsKeyDown(ControllerType::Mouse, 0, g_rightButton);
			bool pressed = down && !g_rightDown;
			g_rightDown = down;
			if (g_fakeRight > 0)
			{
				g_fakeRight -= ms;
				if (HWP::ItemActions::TabOpen())
				{
					g_fakeRight = 0;
					pressed = true;
					HWP::Log("chatlinks", "right click stand-in: " + HoveredItemName());
				}
			}
			if (pressed && HWP::ItemActions::TabOpen())
				LinkHovered("right click");
		}

		// --- the linked items panel -----------------------------------------------------------

		// the cursor in HUD units (HUDAnnounceLoot)
		vec2 HUDMouse()
		{
			return GetGameModeMousePosition() / g_gameMode.m_wndScale;
		}

		bool Inside(const vec4 &in r, const vec2 &in p)
		{
			return p.x >= r.x && p.y >= r.y && p.x < r.x + r.z && p.y < r.y + r.w;
		}

		string RectStr(const vec4 &in r)
		{
			return int(r.x) + "," + int(r.y) + " " + int(r.z) + "x" + int(r.w);
		}

		// hwp chatlinks: the status (links, the panel and its lines' rects, the cursor, the
		// hover); hwp chatlinks rclick: the right-click stand-in (g_fakeRight)
		void CmdChatLinks(array<string>@ args)
		{
			if (args.length() > 0 && args[0] == "rclick")
			{
				g_fakeRight = 3000;
				HWP::Commands::Reply("chatlinks: right click armed");
				return;
			}
			auto gm = cast<BaseGameMode>(g_gameMode);
			Linked@ hovered = g_hud is null ? null : g_hud.m_hovered;
			bool ours = gm !is null && hovered !is null && gm.m_windowManager.m_tooltip is hovered.m_tip;
			vec2 mouse = HUDMouse();
			string ret = "chatlinks: " + (Enabled() ? "on" : "off") + ", links " + g_links.length() + " announced " + g_announced
				+ " tips " + g_tips + " by action " + g_byAction + " by right " + g_byRight + " rbutton " + g_rightButton
				+ "; tab item " + HoveredItemName()
				+ "; hovered " + (hovered is null ? "none" : hovered.m_item.GetName())
				+ "; tooltip " + (gm is null || gm.m_windowManager.m_tooltip is null ? "none" : (ours ? "ours" : "other"))
				+ "; mouse " + int(mouse.x) + "," + int(mouse.y);
			if (g_hud is null)
				ret += "; no panel";
			else
			{
				ret += "; panel " + (g_hud.m_visible ? "shown" : "hidden") + " " + RectStr(g_hud.PanelRect());
				for (uint i = 0; i < g_hud.m_shown.length(); i++)
					ret += "; line " + i + " " + g_hud.m_shown[i].m_item.GetName() + " " + RectStr(g_hud.LineRect(i));
			}
			HWP::Commands::Reply(ret);
		}

		// hwp links: the panel again
		void CmdLinks(array<string>@ args)
		{
			if (g_hud is null || g_links.length() == 0)
			{
				HWP::Commands::Reply(Resources::GetString(".hwp.chatlinks.none"));
				return;
			}
			g_hud.Show();
		}

		void CmdLink(array<string>@ args)
		{
			if (!Enabled())
			{
				HWP::Commands::Reply(Resources::GetString(".hwp.chatlinks.off"));
				return;
			}
			auto plr = GetLocalPlayerRecord();
			if (plr is null || plr.equipped is null)
				return;
			string slotName = args.length() > 0 ? args[0] : "main";
			int slot = SlotFromName(slotName);
			Item::Item@ item = plr.equipped.m_items[slot];
			if (item is null)
			{
				HWP::Commands::Reply(Resources::GetString(".hwp.chatlinks.nothing", { { "slot", slotName } }));
				return;
			}
			LinkItem(plr, item);
		}
	}
}

// The linked items above the chat: the last MAX_LINKS links, oldest on top, each in
// its quality colour; the cursor on one shows the item's tooltip.
class HWPChatLinksHUD : HUDComponent
{
	array<TextWidget@> m_lines;
	Widget@ m_root;
	Widget@ m_panel;
	array<HWP::ChatLinks::Linked@> m_shown;
	HWP::ChatLinks::Linked@ m_hovered;
	int m_left = 0;

	HWPChatLinksHUD(GUIBuilder@ b)
	{
		super(b, "gui/hwp_chatlinks.gui");
		for (uint i = 0; i < HWP::ChatLinks::MAX_LINKS; i++)
			m_lines.insertLast(cast<TextWidget>(m_widget.GetWidgetById("line" + i)));
		@m_root = m_widget.GetWidgetById("root");
		@m_panel = m_widget.GetWidgetById("panel");
		m_visible = false;
		// under the window manager's tooltip, which shows the hovered link
		m_drawOnTop = false;
	}

	void Show()
	{
		m_shown = HWP::ChatLinks::g_links;
		int w = 0;
		for (uint i = 0; i < m_lines.length(); i++)
		{
			m_lines[i].SetText(i < m_shown.length() ? HWP::ChatLinks::Link(m_shown[i].m_item) : "");
			m_lines[i].m_visible = i < m_shown.length();
			if (m_lines[i].m_visible)
				w = max(w, m_lines[i].m_width);
		}
		m_panel.m_width = w + 10;
		m_root.m_width = m_panel.m_width;
		m_panel.m_height = 12 * int(m_shown.length()) + 5;
		m_root.m_height = m_panel.m_height;
		Place();
		m_left = HWP::ChatLinks::SHOW_MS;
		m_visible = m_shown.length() > 0;
		Invalidate();
	}

	// just above the chat box: its anchor, width and scale are the ui_chat_* cvars
	// (InGameChat.Update), its height 190 (gui/main_menu/chat.gui)
	void Place()
	{
		float sw = g_gameMode.m_wndWidth;
		float sh = g_gameMode.m_wndHeight;
		vec2 pos = GetVarVec2("ui_chat_pos");
		float scale = GetVarFloat("ui_chat_scale");
		float chatW = GetVarFloat("ui_chat_width") * sw;
		float x = pos.x * (sw - chatW);
		float y = pos.y * (sh - 190 * scale) - m_root.m_height - 2;
		vec2 at = vec2(int(x), int(max(2.0f, y)));
		if (at.x != m_root.m_offset.x || at.y != m_root.m_offset.y)
		{
			m_root.m_offset = at;
			Invalidate();
		}
	}

	vec4 PanelRect()
	{
		return vec4(m_panel.m_origin.x, m_panel.m_origin.y, m_panel.m_width, m_panel.m_height);
	}

	// a line's row: the panel's width, so the gap after a short name still counts
	vec4 LineRect(uint i)
	{
		return vec4(m_panel.m_origin.x, m_lines[i].m_origin.y - 1, m_panel.m_width, 12);
	}

	// the line under the cursor, -1 for none
	int Under()
	{
		if (!m_visible || !HWP::ChatLinks::Enabled())
			return -1;
		auto input = GetInput();
		if (input !is null && input.UsingGamepad)
			return -1;
		vec2 mouse = HWP::ChatLinks::HUDMouse();
		for (uint i = 0; i < m_shown.length() && i < m_lines.length(); i++)
			if (HWP::ChatLinks::Inside(LineRect(i), mouse))
				return int(i);
		return -1;
	}

	// beside the line, right of the panel, its top on the line's (as an inventory item's
	// tooltip sits by the item); the window manager moves it up to keep it on screen
	vec2 TipPos(int i, ITooltip@ tip)
	{
		vec4 r = LineRect(i);
		return vec2(r.x + r.z + 4, r.y);
	}

	void UpdateHover()
	{
		auto gm = cast<BaseGameMode>(g_gameMode);
		if (gm is null || gm.m_windowManager is null)
			return;
		int i = Under();
		HWP::ChatLinks::Linked@ l = i < 0 ? null : m_shown[i];
		if (l is m_hovered)
		{
			// another tooltip took over and closed (a loot log line): ours comes back
			if (l !is null && gm.m_windowManager.m_tooltip is null)
				gm.m_windowManager.SetTooltip(l.m_tip, TipPos(i, l.m_tip));
			return;
		}
		if (m_hovered !is null && gm.m_windowManager.m_tooltip is m_hovered.m_tip)
			gm.m_windowManager.CloseTooltip();
		@m_hovered = l;
		if (l is null)
			return;
		if (l.m_tip is null)
			@l.m_tip = Item::BuildItemTooltip(l.m_item, l.m_item.GetPrice(), 1, false);
		gm.m_windowManager.SetTooltip(l.m_tip, TipPos(i, l.m_tip));
		HWP::ChatLinks::g_tips++;
		HWP::Log("chatlinks", "tooltip: " + l.m_item.GetName());
	}

	void Update(int dt, PlayerRecord@ record) override
	{
		if (m_visible)
		{
			if (!HWP::ChatLinks::Enabled())
				m_left = 0;
			Place();
			UpdateHover();
			if (m_hovered is null)
				m_left -= dt;
			if (m_left <= 0)
			{
				m_visible = false;
				UpdateHover();
			}
		}
		HUDComponent::Update(dt, record);
	}
}

namespace HWPChatLinks
{
	[Hook]
	void HUDConstructor(HUD@ hud, GUIBuilder@ b)
	{
		auto comp = HWPChatLinksHUD(b);
		hud.m_components.insertLast(comp);
		@HWP::ChatLinks::g_hud = comp;
		// the links stay across levels, their tooltips are rebuilt for the new HUD
		for (uint i = 0; i < HWP::ChatLinks::g_links.length(); i++)
			@HWP::ChatLinks::g_links[i].m_tip = null;
	}
}

namespace Modules
{
	class HWPChatLinksModule : Module, IEventPlayerLinkedItem
	{
		HWPChatLinksModule()
		{
			super("hwp-chatlinks");
			GameEvents::Subscribe(this);
			HWP::Commands::Register("link", "[main|off|head|chest|feet|hands|back]  link an equipped item in chat", HWP::Commands::Handler(HWP::ChatLinks::CmdLink));
			HWP::Commands::Register("links", " show the linked items again (hover one for its tooltip)", HWP::Commands::Handler(HWP::ChatLinks::CmdLinks));
			HWP::Commands::Register("chatlinks", "[rclick]  the links, the panel's line rects and the hover state", HWP::Commands::Handler(HWP::ChatLinks::CmdChatLinks));
			HWP::Settings::LocalOnly("chatlinks.key");
			auto link = HWP::ChatLinks::LinkAction();
			HWP::ItemActions::Register(link);
			HWP::Options::Register("linkkey", HWP::ItemActions::ActionKeyOption(link, ".hwp.chatlinks.key"));
		}

		// HWP::Guard (tools/guard_modules.py): a script error here turns this off, not the game
		HWP::Guard m_guardUpdateFrame;
		void UpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused) override
		{
			if (m_guardUpdateFrame.Skip("chatlinks", "HWPChatLinksModule.UpdateFrame"))
				return;
			if (m_guardUpdateFrame.Raw())
			{
				GuardedUpdateFrame(ms, gameInput, menuInput, paused);
				m_guardUpdateFrame.Ok();
				return;
			}
			try { GuardedUpdateFrame(ms, gameInput, menuInput, paused); m_guardUpdateFrame.Ok(); }
			catch { m_guardUpdateFrame.Failed(); }
		}

		void GuardedUpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused)
		{
			HWP::ChatLinks::PollRightClick(ms);
		}

		void OnEventPlayerLinkedItem(PlayerRecord@ plr, Item::Item@ item)
		{
			if (plr is null || item is null || !HWP::ChatLinks::Enabled())
				return;
			HWP::ChatLinks::Announce(plr, item);
		}
	}
}
