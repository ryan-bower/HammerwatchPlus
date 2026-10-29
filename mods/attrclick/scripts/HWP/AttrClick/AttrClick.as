// Attribute point clicks (issue #22): at the Attribute Trainer, Shift+Click places 20 points
// and Ctrl+Click 5, where vanilla places one per click.
//
// The trainer (actors/npcs/town/npc_attrib_trainer.unit) is an AttributeAssignerShopContent:
// a click on a stat runs ShopWindow.OnFunc("buy"), which calls Buy("assign"), one point into
// the record's pickedStr/Dex/Int/Foc/Vit (Town/AttributeAssignerShopContent.as). Holding the
// button repeats Buy, faster and faster. With every level and NG+ level adding points, placing
// dozens meant dozens of clicks. The class swap (module.json) points the trainer unit at
// HWPAttributeAssignerShopContent, whose Buy places PerClick() points at once (never more than
// there are) with one SyncStatPoints. A held button repeats that amount. Its window shows the
// amount on each stat's cost and "Shift 20, Ctrl 5" beside the points left while a mouse is in
// use; a gamepad has no modifier keys and keeps the hold repeat.
//
// `hwp attrclick` shows the points left, the picked points and the amount a click places now;
// `hwp attrclick force shift|ctrl|none|keys` holds a modifier for a test (keys: read the real
// keys again).
namespace HWP
{
	namespace AttrClick
	{
		// SDL scancodes (HWP::Options::KeyName)
		const int SC_LCTRL = 224;
		const int SC_LSHIFT = 225;
		const int SC_RCTRL = 228;
		const int SC_RSHIFT = 229;

		const int SHIFT_POINTS = 20;
		const int CTRL_POINTS = 5;

		bool g_enabled = true;
		string g_force = "keys"; // test aid: shift, ctrl, none, or keys (the real keys)

		void RefreshSettings()
		{
			g_enabled = HWP::Settings::GetBool("attrclick.enabled", true);
		}

		void OnSettingChanged(const string &in key)
		{
			if (key.findFirst("attrclick.") == 0)
				RefreshSettings();
		}

		bool UsingMouse()
		{
			return !GetInput().UsingGamepad;
		}

		// the points one click places: 20 with Shift held, 5 with Ctrl, else 1 (Shift wins)
		int PerClick()
		{
			if (!g_enabled)
				return 1;
			if (g_force == "shift")
				return SHIFT_POINTS;
			if (g_force == "ctrl")
				return CTRL_POINTS;
			if (g_force == "none" || !UsingMouse())
				return 1;
			if (HWP::Options::KeyDown(SC_LSHIFT) || HWP::Options::KeyDown(SC_RSHIFT))
				return SHIFT_POINTS;
			if (HWP::Options::KeyDown(SC_LCTRL) || HWP::Options::KeyDown(SC_RCTRL))
				return CTRL_POINTS;
			return 1;
		}

		string Picked(PlayerRecord@ rec)
		{
			return "str " + rec.pickedStr + ", dex " + rec.pickedDex + ", int " + rec.pickedInt
				+ ", foc " + rec.pickedFoc + ", vit " + rec.pickedVit;
		}

		void CmdAttrClick(array<string>@ args)
		{
			if (args.length() > 1 && args[0] == "force")
			{
				if (args[1] == "shift" || args[1] == "ctrl" || args[1] == "none" || args[1] == "keys")
					g_force = args[1];
			}
			auto rec = GetLocalPlayerRecord();
			string line = "attribute clicks " + (g_enabled ? "on" : "off") + ", a click places " + PerClick()
				+ " (" + g_force + ")";
			if (rec !is null)
				line += "; " + rec.GetPlaceableStatPoints() + " point(s) to place, picked " + Picked(rec);
			HWP::Log("attrclick", line);
			HWP::Commands::Reply(line);
		}
	}
}

class HWPAttributeAssignerShopContent : AttributeAssignerShopContent
{
	HWPAttributeAssignerShopContent(UnitPtr u, SValue& params)
	{
		super(u, params);
	}

	bool Buy(const string &in func, uint hash, IShopItem@ item) override
	{
		auto attribItem = cast<AttributeAssignerShopContentItem>(item);
		int n = min(HWP::AttrClick::PerClick(), m_player.GetPlaceableStatPoints());
		if (n <= 1 || func != "assign" || attribItem is null)
			return AttributeAssignerShopContent::Buy(func, hash, item);

		switch (attribItem.m_stat)
		{
		case Modifiers::ConvertableStat::Str: m_player.pickedStr += n; break;
		case Modifiers::ConvertableStat::Dex: m_player.pickedDex += n; break;
		case Modifiers::ConvertableStat::Int: m_player.pickedInt += n; break;
		case Modifiers::ConvertableStat::Vit: m_player.pickedVit += n; break;
		case Modifiers::ConvertableStat::Foc: m_player.pickedFoc += n; break;
		default: return false;
		}

		m_player.SyncStatPoints();
		m_player.RefreshModifiers();
		HWP::Log("attrclick", "placed " + n + " in " + attribItem.m_id + ", " + m_player.GetPlaceableStatPoints() + " left");
		return true;
	}

	AWindowObject@ MakeShopWindow(GUIBuilder@ guiBuilder) override
	{
		@m_window = HWPAttributeAssignerWindow(guiBuilder, this);
		return m_window;
	}
}

class HWPAttributeAssignerWindow : AttributeAssignerWindow
{
	int m_shownPerClick = -1;
	bool m_shownMouse = false;

	HWPAttributeAssignerWindow(GUIBuilder@ b, AShopContent@ content)
	{
		super(b, content);
	}

	void Refresh() override
	{
		AttributeAssignerWindow::Refresh();

		m_shownPerClick = HWP::AttrClick::PerClick();
		m_shownMouse = HWP::AttrClick::UsingMouse();
		int left = m_shopContent.m_player.GetPlaceableStatPoints();
		if (m_shownPerClick > 1)
		{
			int n = max(1, min(m_shownPerClick, left));
			for (uint i = 0; i < m_itemList.m_children.length(); i++)
			{
				auto button = cast<EntryShopItemWidget>(m_itemList.m_children[i]);
				if (button !is null)
					button.SetCostText("\\\"icn-attrpt\"" + n);
			}
		}
		if (m_currencyText !is null && HWP::AttrClick::g_enabled && m_shownMouse && left > 1)
			m_currencyText.SetText(Resources::GetString(".menu.player.attrib.currpoints", {{ "points", left }})
				+ "  " + Resources::GetString(".hwp.attrclick.hint"));
	}

	bool Update(int ms, GameInput& gameInput, MenuInput& menuInput) override
	{
		// Shift or Ctrl pressed or let go, or the gamepad taken up: the costs and the hint follow
		if (HWP::AttrClick::PerClick() != m_shownPerClick || HWP::AttrClick::UsingMouse() != m_shownMouse)
			Refresh();
		return AttributeAssignerWindow::Update(ms, gameInput, menuInput);
	}
}

namespace Modules
{
	class HWPAttrClickModule : Module, HWP::ModuleStart
	{
		HWPAttrClickModule()
		{
			super("hwp-attrclick");
			HWP::Commands::OnSettingChanged(HWP::Commands::SettingListener(HWP::AttrClick::OnSettingChanged));
			HWP::Commands::Register("attrclick", "[force shift|ctrl|none|keys]  attribute point clicks: the points left and picked, and what a click places now; force holds a modifier for a test", HWP::Commands::Handler(HWP::AttrClick::CmdAttrClick));
			HWP::AttrClick::RefreshSettings();
			HWP::Log("attrclick", "self-check done: " + (HWP::AttrClick::g_enabled ? "on" : "off") + ", Shift " + HWP::AttrClick::SHIFT_POINTS + ", Ctrl " + HWP::AttrClick::CTRL_POINTS);
		}

		void Start(StartMode sMode)
		{
			HWP::AttrClick::RefreshSettings();
		}
	}
}
