// Drop key for the inventory: with an inventory item hovered in the player
// menu, the key (default Q, SDL scancode 20) drops it at your feet, next to
// vanilla Destroy. Drop is an hwplib item action (ItemActions, DropAction): hwplib's
// inventory shows its hint and polls its key raw, like the other bag actions. The key
// is rebound in the Plus tab (dropkey) and named as on a US keyboard.
//
// droptrade.enabled (host, default on) off: no Drop hint or key, and the use key
// is vanilla again (no pickup first); an item action (Eat) keeps working.
// droptrade.pickup_first (each player's own, default on) turns pickup first off alone.
namespace HWP
{
	namespace DropTrade
	{
		const int DEFAULT_SCANCODE = 20; // SDL scancode for Q

		// unused since 2026-10-28 (hwplib's tab: ItemActions::g_tab); kept for a Character.as
		// override from an older package
		PlayerMenuCharacterTab@ g_tab;
		int g_scancode = DEFAULT_SCANCODE;
		bool g_enabled = true;
		bool g_pickupFirst = true;

		void LoadKey()
		{
			g_scancode = HWP::Settings::GetInt("droptrade.key", DEFAULT_SCANCODE);
		}

		// the drop key's name (US keycap); `hwp dropkey <code> <name>` can name it by hand
		// fit: the short name when the full one is too long for the options value column
		string KeyName(bool fit = false)
		{
			string name = HWP::Settings::GetString("droptrade.keyname", "");
			if (!name.isEmpty())
				return HWP::Options::Escape(name);
			return fit ? HWP::Options::FitKeyName(g_scancode) : HWP::Options::KeyName(g_scancode);
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
			string Value() override { return KeyName(true); }
			void SetScancode(int scancode) override
			{
				if (scancode == DEFAULT_SCANCODE)
					HWP::Settings::Reset("droptrade.key");
				else
					HWP::Settings::SetInt("droptrade.key", scancode);
				HWP::Settings::Reset("droptrade.keyname");
				LoadKey();
				// the new key is held right now (just pressed to bind it): no drop
				HWP::ItemActions::HeldNow(scancode);
			}
		}

		// Drop the hovered bag item at your feet, no dialog. Clients send a DropItem
		// request to the host, which spawns it for everyone.
		class DropAction : HWP::ItemActions::Action
		{
			string Id() override { return "drop"; }
			int Scancode() override { return g_scancode; }
			string KeyName() override { return HWP::DropTrade::KeyName(); }
			int Order() override { return 10; }

			string Label(Equipment::Equipment@ item) override
			{
				return g_enabled ? Resources::GetString(".hwp.droptrade.drop") : "";
			}

			void Do(PlayerRecord@ record, Equipment::Equipment@ item) override
			{
				if (record.actor is null || !record.actor.m_unit.IsValid())
					return;
				// take it out of the bag first: a stale widget whose item already
				// left the bag must not spawn a copy
				if (!record.equipInventory.Remove(item))
					return;
				Item::DropItem(item, record.actor.m_unit.GetPosition(), 1, true, null);
				HWP::Log("droptrade", "dropped " + item.GetName());
			}
		}

		// ---- kept for a Character.as / EquipmentItemWidget.as override from a package
		// older than 2026-10-28 (hwplib's own overrides use ItemActions) ----
		string NavText()
		{
			return "[" + KeyName() + "] " + Resources::GetString(".hwp.droptrade.drop");
		}

		string ActionNavText(Equipment::Equipment@ item)
		{
			string label = HWP::ItemActions::Label(item);
			return label == "" ? "" : "[E] " + label;
		}

		void MakeButton(KeyNavigationText@ text, WindowInput::OnFunc@ func)
		{
			HWP::ItemActions::MakeButton(text, func);
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
			HWP::ItemActions::Register(HWP::DropTrade::DropAction());
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
			if (HWP::DropTrade::g_enabled && HWP::DropTrade::g_pickupFirst)
				HWP::PickupFirst::Update();
		}
	}
}
