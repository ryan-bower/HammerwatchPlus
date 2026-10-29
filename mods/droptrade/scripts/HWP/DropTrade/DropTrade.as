// Drop key for the inventory: with an inventory item hovered in the player
// menu, the key (default Q, SDL scancode 20) drops it at your feet, next to
// vanilla Destroy. The menu's own bindings have no free action for it, so
// the key is polled raw like the weapon swap key. The item action key (Eat,
// default E, scancode 8) the same way. Both are rebound in the Plus tab
// (dropkey, actionkey) and named as the player's keyboard labels them.
//
// droptrade.enabled (host, default on) off: no Drop hint or key, and the use key
// is vanilla again (no pickup first); an item action (Eat) keeps working.
// droptrade.pickup_first (each player's own, default on) turns pickup first off alone.
namespace HWP
{
	namespace DropTrade
	{
		const int DEFAULT_SCANCODE = 20; // SDL scancode for Q

		PlayerMenuCharacterTab@ g_tab;
		int g_scancode = DEFAULT_SCANCODE;
		bool g_wasDown = false;
		bool g_enabled = true;
		bool g_pickupFirst = true;

		void LoadKey()
		{
			g_scancode = HWP::Settings::GetInt("droptrade.key", DEFAULT_SCANCODE);
			g_actionScancode = HWP::Settings::GetInt("droptrade.actionkey", DEFAULT_ACTION_SCANCODE);
		}

		// the drop key's name on this keyboard (read live: a label learned later shows at
		// once); `hwp dropkey <code> <name>` can name it by hand
		string KeyName()
		{
			string name = HWP::Settings::GetString("droptrade.keyname", "");
			return name.isEmpty() ? HWP::Options::KeyName(g_scancode) : HWP::Options::Escape(name);
		}

		void RefreshSettings()
		{
			g_enabled = HWP::Settings::GetBool("droptrade.enabled", true);
			g_pickupFirst = HWP::Settings::GetBool("droptrade.pickup_first", true);
			LoadKey();
		}

		void OnSettingChanged(const string &in key)
		{
			if (key.findFirst("droptrade.") == 0)
				RefreshSettings();
		}

		bool Enabled() { return g_enabled; }

		// the row in the player menu's HammerwatchPlus tab: click, then press the new key
		class DropKeyOption : HWP::Options::KeyOption
		{
			string Title() override { return Resources::GetString(".hwp.droptrade.option"); }
			int Scancode() override { return g_scancode; }
			string Value() override { return KeyName(); }
			void SetScancode(int scancode) override
			{
				if (scancode == DEFAULT_SCANCODE)
					HWP::Settings::Reset("droptrade.key");
				else
					HWP::Settings::SetInt("droptrade.key", scancode);
				HWP::Settings::Reset("droptrade.keyname");
				LoadKey();
				// the new key is held right now (just pressed to bind it): no drop
				g_wasDown = true;
			}
		}

		string NavText()
		{
			return "[" + KeyName() + "] " + Resources::GetString(".hwp.droptrade.drop");
		}

		// the item action key (core ItemActions: Eat on a fish), default E
		const int DEFAULT_ACTION_SCANCODE = 8; // SDL scancode for E
		int g_actionScancode = DEFAULT_ACTION_SCANCODE;
		bool g_actionWasDown = false;

		class ActionKeyOption : HWP::Options::KeyOption
		{
			string Title() override { return Resources::GetString(".hwp.droptrade.action_option"); }
			int Scancode() override { return g_actionScancode; }
			void SetScancode(int scancode) override
			{
				if (scancode == DEFAULT_ACTION_SCANCODE)
					HWP::Settings::Reset("droptrade.actionkey");
				else
					HWP::Settings::SetInt("droptrade.actionkey", scancode);
				LoadKey();
				// the new key is held right now (just pressed to bind it): no action
				g_actionWasDown = true;
			}
		}

		string ActionNavText(Equipment::Equipment@ item)
		{
			string label = HWP::ItemActions::Label(item);
			return label == "" ? "" : "[" + HWP::Options::KeyName(g_actionScancode) + "] " + label;
		}

		void MakeButton(KeyNavigationText@ text, WindowInput::OnFunc@ func)
		{
			@text.m_func = func;
			@text.m_hoverSnd = Resources::GetSoundEvent("event:/sfx/ui/hover");
			@text.m_clickSnd = Resources::GetSoundEvent("event:/sfx/ui/click");
		}

		bool TypingInChat()
		{
			auto main = cast<MainMenuGameMode>(g_gameMode);
			return main !is null && main.m_wChat !is null && main.m_wChat.m_wInput !is null && main.m_wChat.m_wInput.m_typing;
		}

		// true while the character tab is open and on top: not behind a dialog
		// (the vanilla destroy confirm), and no text input has the keyboard,
		// since the raw key poll cannot tell the drop key from typing a 'q'
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

		void Poll()
		{
			bool down = Platform::IsKeyDown(ControllerType::Keyboard, 0, g_scancode);
			bool pressed = down && !g_wasDown;
			g_wasDown = down;
			if (pressed && g_enabled && TabOpen())
				g_tab.HWPDrop();
			bool aDown = Platform::IsKeyDown(ControllerType::Keyboard, 0, g_actionScancode);
			bool aPressed = aDown && !g_actionWasDown;
			g_actionWasDown = aDown;
			if (aPressed && TabOpen())
				g_tab.HWPAction();
		}

		void CmdDropKey(array<string>@ args)
		{
			if (args.length() >= 1)
			{
				int code = parseInt(args[0]);
				if (code <= 0)
				{
					HWP::Commands::Reply(Resources::GetString(".hwp.droptrade.key_usage"));
					return;
				}
				HWP::Settings::SetInt("droptrade.key", code);
				if (args.length() >= 2)
					HWP::Settings::SetString("droptrade.keyname", args[1].toUpper());
				else
					HWP::Settings::Reset("droptrade.keyname");
				LoadKey();
			}
			HWP::Commands::Reply(Resources::GetString(".hwp.droptrade.key", { { "code", "" + g_scancode }, { "name", KeyName() } }));
		}
	}
}

namespace Modules
{
	class HWPDropTradeModule : Module, HWP::ModuleStart
	{
		HWPDropTradeModule()
		{
			super("hwp-droptrade");
			HWP::Commands::Register("dropkey", "[scancode [name]]  show or set the inventory drop key", HWP::Commands::Handler(HWP::DropTrade::CmdDropKey));
			HWP::Options::Register("dropkey", HWP::DropTrade::DropKeyOption());
			HWP::Options::Register("actionkey", HWP::DropTrade::ActionKeyOption());
			HWP::Commands::OnSettingChanged(HWP::Commands::SettingListener(HWP::DropTrade::OnSettingChanged));
			HWP::Log("droptrade", "menu destroy key " + FormatKeyName(GetActionBinding("MenuAdditional")));
		}

		void Start(StartMode sMode)
		{
			HWP::DropTrade::RefreshSettings();
		}

		// HWP::Guard (tools/guard_modules.py): a script error here turns this off, not the game
		HWP::Guard m_guardUpdateFrame;
		void UpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused) override
		{
			if (m_guardUpdateFrame.Skip("droptrade", "HWPDropTradeModule.UpdateFrame"))
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
			HWP::DropTrade::Poll();
			if (HWP::DropTrade::g_enabled && HWP::DropTrade::g_pickupFirst)
				HWP::PickupFirst::Update();
		}
	}
}
