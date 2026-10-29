// Extra actions on a bag item (drop it, eat a fish, send it home with the pet, ...). A
// module registers an Action in its ctor (script globals reset every level). The
// inventory (hwplib's Character tab and EquipmentItemWidget overrides, so every package
// has them) shows one key hint per action that has a label for the hovered item, after
// vanilla Equip / Compare / Destroy and in Order(); each hint is clickable and the
// action's key does it while the character tab is on top (Poll, from the core module).
//
// Before 2026-10-28 droptrade owned the hints and only the first action showed, on a
// fixed E, which is also the menu's own Destroy key (MenuAdditional in
// controls_default.cfg). A KeyedAction keeps its key in a setting the player rebinds
// from the Plus tab (its ActionKeyOption); every key here must be one the menu does not
// bind (CheckKeys logs a clash).
namespace HWP
{
	namespace ItemActions
	{
		// the key an Action written before keys existed keeps (the old fixed E)
		const int LEGACY_SCANCODE = 8;

		class Action
		{
			// the hint's verb for this item ("Eat"), or "" when it isn't for this item
			string Label(Equipment::Equipment@ item) { return ""; }
			// do it to the local player's item; the action takes the item out of the bag
			// itself when it is used up
			void Do(PlayerRecord@ record, Equipment::Equipment@ item) {}
			// added 2026-10-28 (the library only grows: an older Action keeps these defaults)
			// a short id for logs and HWPActionId ("drop", "eat", "courier")
			string Id() { return "action"; }
			// the SDL scancode that does it on the hovered item; 0 = none (the hint still clicks)
			int Scancode() { return LEGACY_SCANCODE; }
			// the key as the hint prints it
			string KeyName() { return HWP::Options::KeyName(Scancode()); }
			// the hint's place, lower first (Drop 10, Eat 20, Send home 30)
			int Order() { return 50; }
		}

		// an action whose key is the setting m_setting (default m_default)
		class KeyedAction : Action
		{
			string m_setting;
			int m_default;

			KeyedAction(const string &in setting, int def)
			{
				m_setting = setting;
				m_default = def;
			}

			int Scancode() override { return HWP::Settings::GetInt(m_setting, m_default); }
		}

		// the Plus tab row that rebinds a KeyedAction: click, then press the new key.
		// The module registers it (HWP::Options::Register) under the id its config names.
		class ActionKeyOption : HWP::Options::KeyOption
		{
			KeyedAction@ m_action;
			string m_title; // lang key

			ActionKeyOption(KeyedAction@ action, const string &in title)
			{
				@m_action = action;
				m_title = title;
			}

			string Title() override { return Resources::GetString(m_title); }
			int Scancode() override { return m_action.Scancode(); }
			void SetScancode(int scancode) override
			{
				if (scancode == m_action.m_default)
					HWP::Settings::Reset(m_action.m_setting);
				else
					HWP::Settings::SetInt(m_action.m_setting, scancode);
				// the new key is held right now (just pressed to bind it): it must not act
				HeldNow(scancode);
			}
		}

		array<Action@> g_actions;

		void Register(Action@ action)
		{
			g_actions.insertLast(action);
		}

		// every action for this item, in hint order (stable for equal orders)
		array<Action@>@ AllFor(Equipment::Equipment@ item)
		{
			array<Action@> list;
			if (item is null)
				return list;
			for (uint i = 0; i < g_actions.length(); i++)
			{
				if (g_actions[i].Label(item) == "")
					continue;
				uint at = list.length();
				while (at > 0 && list[at - 1].Order() > g_actions[i].Order())
					at--;
				list.insertAt(at, g_actions[i]);
			}
			return list;
		}

		// the first action for the item (what the single hint used to show)
		Action@ For(Equipment::Equipment@ item)
		{
			auto list = AllFor(item);
			return list.length() == 0 ? null : list[0];
		}

		string Label(Equipment::Equipment@ item)
		{
			auto a = For(item);
			return a is null ? "" : a.Label(item);
		}

		// the hint texts for the item, "[Q] Drop", in AllFor order
		array<string>@ NavTexts(Equipment::Equipment@ item)
		{
			array<string> texts;
			auto list = AllFor(item);
			for (uint i = 0; i < list.length(); i++)
			{
				string key = list[i].Scancode() > 0 ? "[" + list[i].KeyName() + "] " : "";
				texts.insertLast(key + list[i].Label(item));
			}
			return texts;
		}

		// true when the action ran
		bool DoAction(PlayerRecord@ record, Equipment::Equipment@ item, Action@ a)
		{
			if (a is null || record is null || item is null || a.Label(item) == "")
				return false;
			a.Do(record, item);
			HWP::Gear::Changed();
			return true;
		}

		// the first action (the old single hint); true when an action ran
		bool Do(PlayerRecord@ record, Equipment::Equipment@ item)
		{
			return DoAction(record, item, For(item));
		}

		// a navigation bar hint that runs func when clicked
		void MakeButton(KeyNavigationText@ text, WindowInput::OnFunc@ func)
		{
			@text.m_func = func;
			@text.m_hoverSnd = Resources::GetSoundEvent("event:/sfx/ui/hover");
			@text.m_clickSnd = Resources::GetSoundEvent("event:/sfx/ui/click");
		}

		// the hint bar kept on screen: vanilla centres it under the window, and the player
		// menu sits at the right edge, so a bag item's bar (Destroy, then the item actions)
		// ran off it and hid the last hints
		class FitNavBar : KeyNavigationBar
		{
			FitNavBar(AWindowObject@ windowObject) { super(windowObject); }

			void Draw(SpriteBatch& sb, vec2 pos, int width) override
			{
				int maxWidth = max(width, GetWidth());
				int left = int(pos.x) - int(maxWidth * 0.5f);
				int hi = max(2, int(g_gameMode.m_wndWidth) - 2 - maxWidth);
				int fit = left < 2 ? 2 : (left > hi ? hi : left);
				KeyNavigationBar::Draw(sb, pos + vec2(fit - left, 0), width);
			}
		}

		// the window's hint bar as a FitNavBar, its texts kept (once per window)
		void FitBar(AWindowObject@ host)
		{
			if (host is null || host.m_navigationBar is null || cast<FitNavBar>(host.m_navigationBar) !is null)
				return;
			FitNavBar@ bar = FitNavBar(host);
			for (uint i = 0; i < bar.m_texts.length(); i++)
				bar.m_texts[i].m_text.Cleanup();
			bar.m_texts = host.m_navigationBar.m_texts;
			bar.m_visible = host.m_navigationBar.m_visible;
			@host.m_navigationBar = bar;
		}

		// ---- keys ----------------------------------------------------------------

		PlayerMenuCharacterTab@ g_tab; // set by the Character tab's ctor
		array<bool> g_down(256, false);

		void HeldNow(int scancode)
		{
			if (scancode > 0 && scancode < int(g_down.length()))
				g_down[scancode] = true;
		}

		bool TypingInChat()
		{
			auto main = cast<MainMenuGameMode>(g_gameMode);
			return main !is null && main.m_wChat !is null && main.m_wChat.m_wInput !is null && main.m_wChat.m_wInput.m_typing;
		}

		// true while the character tab is open and on top: not behind a dialog
		// (the vanilla destroy confirm), and no text input has the keyboard,
		// since a raw key poll cannot tell an action key from typing that letter
		bool TabOpen()
		{
			auto gm = cast<BaseGameMode>(g_gameMode);
			if (g_tab is null || gm is null || gm.m_windowManager is null || gm.m_windowManager.m_objects.length() == 0)
				return false;
			auto cb = GetControlBindings();
			if ((cb !is null && cb.IsExpectingTextInput()) || TypingInChat())
				return false;
			auto menu = cast<PlayerMenu>(gm.m_windowManager.m_objects[gm.m_windowManager.m_objects.length() - 1]);
			return menu !is null && menu.m_tabSystem !is null
				&& menu.m_tabSystem.m_currentIndex >= 0 && menu.m_tabSystem.m_currentIndex < int(menu.m_tabSystem.m_tabs.length())
				&& menu.m_tabSystem.m_tabs[menu.m_tabSystem.m_currentIndex] is g_tab;
		}

		// every frame (core module): an action key pressed with the tab on top does the
		// first action for the hovered item that has that key
		void Poll()
		{
			for (uint i = 0; i < g_actions.length(); i++)
			{
				int sc = g_actions[i].Scancode();
				if (sc <= 0 || sc >= int(g_down.length()))
					continue;
				// two actions on one key: read the key once a frame
				bool seen = false;
				for (uint j = 0; j < i && !seen; j++)
					seen = g_actions[j].Scancode() == sc;
				if (seen)
					continue;
				bool down = Platform::IsKeyDown(ControllerType::Keyboard, 0, sc);
				bool pressed = down && !g_down[sc];
				g_down[sc] = down;
				if (pressed && TabOpen())
					g_tab.HWPActionKey(sc);
			}
		}

		// the menu actions an action key must not share a key with
		array<string> MENU_ACTIONS = { "MenuAdditional", "MenuContext", "MenuForward", "MenuAccept", "MenuBack", "MenuChatAll", "PlayerMenu", "MenuToggle" };

		// the menu action bound to this key name ("e" -> MenuAdditional), or ""
		string MenuClash(const string &in keyName)
		{
			// every binding of the current map: GetActionBinding returns only an action's first
			// key, and PlayerMenu has two (I and C)
			auto input = GetInput();
			if (input is null)
				return "";
			auto map = input.GetCurrentMap();
			if (map is null)
				return "";
			string k = keyName.toLower();
			auto bindings = map.GetBindings();
			for (uint i = 0; i < bindings.length(); i++)
			{
				if (MENU_ACTIONS.find(bindings[i].Action) >= 0 && bindings[i].ID.toLower() == k)
					return bindings[i].Action;
			}
			return "";
		}

		// self-check (core, first town frame): log each action's key and a clash with a menu key
		void CheckKeys()
		{
			for (uint i = 0; i < g_actions.length(); i++)
			{
				auto a = g_actions[i];
				if (a.Scancode() <= 0)
					continue;
				string clash = MenuClash(a.KeyName());
				string line = "item action " + a.Id() + " key " + a.KeyName() + " (" + a.Scancode() + ")"
					+ (clash == "" ? "" : " CLASHES with the menu's " + clash + " key");
				HWP::Log("core", line);
				if (g_replying)
					HWP::Commands::Reply(line);
			}
		}

		bool g_replying = false;

		// hwp itemkeys: the same check, now (after a rebind)
		void CmdItemKeys(array<string>@ args)
		{
			if (g_actions.length() == 0)
				HWP::Commands::Reply("no item actions registered");
			g_replying = true;
			CheckKeys();
			g_replying = false;
		}

		void Init()
		{
			HWP::Commands::Register("itemkeys", " list the bag item action keys and any clash with a menu key",
				HWP::Commands::Handler(CmdItemKeys));
		}
	}
}
