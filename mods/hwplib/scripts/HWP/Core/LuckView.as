// HWP::LuckView: what the base library shows of the Luck stat, which lives in the
// hwplib-luck library part (HWP::Luck). The character screen and the Modifications tab
// belong to the base, so they ask a provider the Luck part registers; a package without
// Luck registers none, and the Luck stat and row stay hidden.
//
// The library only grows: Provider keeps these four methods for good (a package built
// against an older copy must still implement it), a new one would be a second interface.
namespace HWP
{
	namespace LuckView
	{
		interface Provider
		{
			float OfRecord(PlayerRecord@ rec);
			float PartyFactor();
			string Fmt(float f);
			string TooltipText(float luck);
		}

		Provider@ g_provider;

		// script globals reset per level: the Luck module calls this from its ctor
		void Set(Provider@ p) { @g_provider = p; }
	}
}

// The Luck value on the character tab's stat bar (gui/playermenu/character.gui, beside
// movement speed): a text that reads the local player's Luck each frame, and the hover tooltip
// of the button it sits in (tooltip-enabled) with the factor it gives. Without a provider the
// button hides.
class HWPLuckStatWidget : TextWidget
{
	int m_shown = -999999;
	string m_shownParty;

	HWPLuckStatWidget()
	{
		super();
	}

	Widget@ Clone() override
	{
		HWPLuckStatWidget@ w = HWPLuckStatWidget();
		CloneInto(w);
		return w;
	}

	void Update(int dt) override
	{
		auto luckView = HWP::LuckView::g_provider;
		if (m_parent !is null)
			m_parent.m_visible = luckView !is null;
		if (luckView is null)
			return;
		auto rec = GetLocalPlayerRecord();
		float luck = luckView.OfRecord(rec);
		int n = int(luck + (luck < 0 ? -0.5f : 0.5f));
		string party = luckView.Fmt(luckView.PartyFactor());
		if (n != m_shown || party != m_shownParty)
		{
			m_shown = n;
			m_shownParty = party;
			SetText("" + n);
			if (m_parent !is null && m_parent.m_tooltip !is null)
				m_parent.m_tooltip.m_tooltipText = luckView.TooltipText(luck);
		}
		TextWidget::Update(dt);
	}
}

ref@ LoadHWPLuckStatWidget(WidgetLoadingContext &ctx)
{
	HWPLuckStatWidget@ w = HWPLuckStatWidget();
	w.Load(ctx);
	return w;
}

namespace HWPLuckView
{
	[Hook]
	void LoadWidgetProducers(GUIBuilder@ builder)
	{
		builder.AddWidgetProducer("hwp-luck-stat", LoadHWPLuckStatWidget);
	}
}
