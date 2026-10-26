// A Way Gate's interact (doodads/hwp/hwp_waygate.unit): the list of the town's gates
// (HWP::WayGates::g_gates, WayGatesModule.as), one button each; the gate the player
// stands at is greyed. A pick closes the window and moves the local player there.
class HWPWayGateShop : AShopContent
{
	HWPWayGateShop() {}
	HWPWayGateShop(UnitPtr u, SValue& params) { super(u, params); }

	bool CanInteract(PlayerRecord@ player) override
	{
		return HWP::WayGates::g_enabled;
	}

	AWindowObject@ MakeShopWindow(GUIBuilder@ guiBuilder) override
	{
		@m_window = HWPWayGateMenu(guiBuilder, this);
		return m_window;
	}

	string GetName() override { return "waygate"; }
	UsableIcon GetIcon() override { return UsableIcon::Generic; }
}

class HWPWayGateMenu : AWindowObject
{
	HWPWayGateShop@ m_shop;
	Widget@ m_list;
	Widget@ m_template;
	int m_here = -1;

	HWPWayGateMenu(GUIBuilder@ b, HWPWayGateShop@ shop)
	{
		super(b, "gui/hwp_waygates.gui");
		@m_shop = shop;
		@m_list = m_widget.GetWidgetById("list");
		@m_template = m_widget.GetWidgetById("template");
		if (shop.m_unit.IsValid())
			m_here = HWP::WayGates::Here(xy(shop.m_unit.GetPosition()));
		Fill();
	}

	void Fill()
	{
		if (m_list is null || m_template is null)
			return;
		m_list.ClearChildren();
		auto gates = HWP::WayGates::g_gates;
		for (uint i = 0; i < gates.length(); i++)
		{
			auto btn = cast<ScalableSpriteButtonWidget>(m_template.Clone());
			if (btn is null)
				continue;
			btn.m_visible = true;
			btn.m_id = "hwp-waygate-" + i;
			btn.m_idHash = HashString(btn.m_id); // GetWidgetById matches children by the hash
			btn.m_func = "go " + i;
			btn.m_navPos = ivec2(int(i % 2), int(i / 2) + 1);
			btn.SetText(gates[i].name);
			btn.m_enabled = int(i) != m_here;
			m_list.AddChild(btn);
		}
		DoLayout();
		RefreshInteractableWidgets(m_widget);
	}

	void OnFunc(Widget@ sender, const string &in name) override
	{
		if (name == "close")
		{
			m_closing = true; // the gate's IsDone() reads it; CloseWindow doesn't set it
			m_manager.CloseWindow(this);
			return;
		}
		auto parse = name.split(" ");
		if (parse.length() == 2 && parse[0] == "go")
		{
			int n = parseInt(parse[1]);
			m_closing = true;
			m_manager.CloseWindow(this);
			HWP::WayGates::Go(n);
			return;
		}
	}
}
