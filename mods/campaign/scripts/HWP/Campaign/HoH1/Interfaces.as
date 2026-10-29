// HoH1's two OpenInterface windows in the tower (tools/import_hoh1.py CLASS_MAP), on
// HoH1's own .gui files: the gambler room's ItemDealer and the dragon floor's EndOfGame.
// HoH2 has neither class, and OpenInterface hits a null pointer on a class it can't make.
// HoH1's items are HoH2 trinkets here (HoH1Item), so the gambler bets trinkets.

// HoH1's "scrollrect": a rect whose children scroll (the dealer's item list, the end
// story). HoH2 kept ScrollableWidget but dropped the producer; the importer renames the
// tag (tools/hoh1_convert.py GUI_TAGS).
class HoH1ScrollableRectWidget : ScrollableWidget
{
	vec4 m_color;
	vec4 m_shadowColor;
	int m_shadowSize;
	SpriteRect@ m_spriteRect;

	HoH1ScrollableRectWidget()
	{
		super();
	}

	Widget@ Clone() override
	{
		HoH1ScrollableRectWidget@ w = HoH1ScrollableRectWidget();
		CloneInto(w);
		return w;
	}

	void Load(WidgetLoadingContext &ctx) override
	{
		LoadWidthHeight(ctx);

		m_color = ctx.GetColorRGBA("color", false, vec4(0, 0, 0, 0));
		m_shadowColor = ctx.GetColorRGBA("shadow", false, vec4(0, 0, 0, 0.5f));
		m_shadowSize = ctx.GetInteger("shadowsize", false, 0);

		string spriteset = ctx.GetString("spriteset", false, "");
		if (spriteset != "")
			@m_spriteRect = SpriteRect(spriteset);

		ScrollableWidget::Load(ctx);
	}

	void DoDraw(SpriteBatch& sb, vec2 pos) override
	{
		ScrollableWidget::DoDraw(sb, pos);

		vec4 p = vec4(pos.x, pos.y, m_width, m_height);
		sb.DrawSprite(null, p, p, m_color);

		if (m_shadowSize > 0 && m_shadowColor.a > 0)
		{
			vec4 sp;
			sp = vec4(pos.x, pos.y, m_width, m_shadowSize); sb.DrawSprite(null, sp, sp, m_shadowColor);
			sp = vec4(pos.x, pos.y + m_shadowSize, m_shadowSize, m_height - m_shadowSize); sb.DrawSprite(null, sp, sp, m_shadowColor);
		}

		if (m_spriteRect !is null)
			m_spriteRect.Draw(sb, pos, m_width, m_height);
	}
}

ref@ LoadHoH1ScrollableRectWidget(WidgetLoadingContext &ctx)
{
	HoH1ScrollableRectWidget@ w = HoH1ScrollableRectWidget();
	w.Load(ctx);
	return w;
}

// HoH1's "scrollbar" (GUI/Scrollbar.as) beside a scrollrect, on HoH1's scrollbar sprites.
// HoH2's own scrollbar is another widget (its sprites, its input) and null-pointers on
// HoH1's markup, so the importer renames the tag (tools/hoh1_convert.py GUI_TAGS). HoH1's
// mouse came through Widget.OnMouseDown and m_hovering, which HoH2 dropped: read here from
// the menu input. The wheel scrolls the rect itself (ScrollableWidget.UpdateInput).
class HoH1ScrollbarWidget : Widget
{
	string m_forId;
	bool m_outsideContainer;
	int m_extraSize;
	ScrollableWidget@ m_wContainer;

	bool m_overHandle;
	int m_overHandleY;

	int m_buttonsSize;
	int m_troughOffset;
	int m_troughSize;

	int m_handleY;
	int m_handleSize;

	vec4 m_colorTrough;
	vec4 m_colorHandle;
	vec4 m_colorHandleHover;
	vec4 m_colorButtons;
	vec4 m_colorButtonsHover;

	Sprite@ m_spriteHandle;
	Sprite@ m_spriteHandleHover;
	Sprite@ m_spriteHandlePressed;

	Sprite@ m_spriteButtonUp;
	Sprite@ m_spriteButtonUpHover;
	Sprite@ m_spriteButtonUpPressed;
	Sprite@ m_spriteButtonUpDisabled;

	Sprite@ m_spriteButtonDown;
	Sprite@ m_spriteButtonDownHover;
	Sprite@ m_spriteButtonDownPressed;
	Sprite@ m_spriteButtonDownDisabled;

	Sprite@ m_spriteTroughTop;
	Sprite@ m_spriteTroughMiddle;
	Sprite@ m_spriteTroughBottom;

	Sprite@ m_spriteTroughDisabledTop;
	Sprite@ m_spriteTroughDisabledMiddle;
	Sprite@ m_spriteTroughDisabledBottom;

	bool m_hovering;
	bool m_handleHover;
	bool m_buttonUpHover;
	bool m_buttonUpPressed;
	bool m_buttonDownHover;
	bool m_buttonDownPressed;

	bool m_hideOnFull;
	int m_handleBorder;

	HoH1ScrollbarWidget()
	{
		super();
	}

	Widget@ Clone() override
	{
		HoH1ScrollbarWidget@ w = HoH1ScrollbarWidget();
		CloneInto(w);
		return w;
	}

	void Load(WidgetLoadingContext &ctx) override
	{
		Widget::Load(ctx);

		GUIDef@ def = ctx.GetGUIDef();

		m_forId = ctx.GetString("forid");
		m_outsideContainer = ctx.GetBoolean("outside", false);
		m_extraSize = ctx.GetInteger("height-add", false);

		m_colorTrough = ctx.GetColorRGBA("color-trough", false, vec4(0, 0, 0, 0));
		m_colorHandle = ctx.GetColorRGBA("color-handle", false, vec4(0, 0.8, 0.5, 0.5));
		m_colorHandleHover = ctx.GetColorRGBA("color-handle-hover", false, m_colorHandle);
		m_colorButtons = ctx.GetColorRGBA("color-buttons", false, vec4(1, 0.8, 0, 0.5));
		m_colorButtonsHover = ctx.GetColorRGBA("color-buttons-hover", false, m_colorButtons);

		string spriteset = ctx.GetString("spriteset", false);
		if (spriteset != "")
		{
			@m_spriteHandle = def.GetSprite(spriteset + "-handle");
			@m_spriteHandleHover = def.GetSprite(spriteset + "-handle-hover");
			@m_spriteHandlePressed = def.GetSprite(spriteset + "-handle-pressed");

			@m_spriteButtonUp = def.GetSprite(spriteset + "-button-up");
			@m_spriteButtonUpHover = def.GetSprite(spriteset + "-button-up-hover");
			@m_spriteButtonUpPressed = def.GetSprite(spriteset + "-button-up-pressed");
			@m_spriteButtonUpDisabled = def.GetSprite(spriteset + "-button-up-disabled");

			@m_spriteButtonDown = def.GetSprite(spriteset + "-button-down");
			@m_spriteButtonDownHover = def.GetSprite(spriteset + "-button-down-hover");
			@m_spriteButtonDownPressed = def.GetSprite(spriteset + "-button-down-pressed");
			@m_spriteButtonDownDisabled = def.GetSprite(spriteset + "-button-down-disabled");

			@m_spriteTroughTop = def.GetSprite(spriteset + "-trough-top");
			@m_spriteTroughMiddle = def.GetSprite(spriteset + "-trough-middle");
			@m_spriteTroughBottom = def.GetSprite(spriteset + "-trough-bottom");

			@m_spriteTroughDisabledTop = def.GetSprite(spriteset + "-trough-disabled-top");
			@m_spriteTroughDisabledMiddle = def.GetSprite(spriteset + "-trough-disabled-middle");
			@m_spriteTroughDisabledBottom = def.GetSprite(spriteset + "-trough-disabled-bottom");
		}

		m_width = 8;
		LoadWidthHeight(ctx, false);

		m_buttonsSize = ctx.GetInteger("buttons-size", false, 8);
		m_troughOffset = ctx.GetInteger("trough-offset", false, m_buttonsSize);
		m_hideOnFull = ctx.GetBoolean("hide-on-full", false);
		m_handleBorder = ctx.GetInteger("handle-border", false, 1);
	}

	void OnMouseDown(vec2 mousePos)
	{
		if (mousePos.y > m_troughOffset + m_handleY && mousePos.y < m_troughOffset + m_handleY + m_handleSize)
		{
			m_overHandle = true;
			m_overHandleY = int(mousePos.y - m_troughOffset) - m_handleY;
		}

		if (m_buttonUpHover)
			m_buttonUpPressed = true;

		if (m_buttonDownHover)
			m_buttonDownPressed = true;
	}

	void DoLayout(vec2 origin, vec2 parentSz) override
	{
		if (m_wContainer is null)
		{
			if (m_parent !is null)
				@m_wContainer = cast<ScrollableWidget>(m_parent.GetWidgetById(m_forId));

			if (m_wContainer is null && m_host !is null && m_host.m_widget !is null)
				@m_wContainer = cast<ScrollableWidget>(m_host.m_widget.GetWidgetById(m_forId));

			if (m_wContainer is null)
			{
				PrintError("Couldn't find scrollbar container for id '" + m_forId + "'");
				Widget::DoLayout(origin, parentSz);
				return;
			}
		}

		m_origin.x = m_wContainer.m_origin.x + m_wContainer.m_width + m_offset.x;
		if (!m_outsideContainer)
			m_origin.x -= m_width;

		m_origin.y = (m_wContainer.m_origin.y - m_extraSize / 2) + m_offset.y;

		m_height = m_wContainer.m_height + m_extraSize;
		m_troughSize = m_height - m_troughOffset * 2;
	}

	void Update(int dt) override
	{
		Widget::Update(dt);

		if (m_wContainer is null)
			return;

		vec2 mousePos = (GetGameModeMousePosition() / g_gameMode.m_wndScale) - m_origin;
		MenuInput@ input = GetMenuInput();

		m_hovering = m_visible && mousePos.x >= 0 && mousePos.y >= 0 && mousePos.x < m_width && mousePos.y < m_height;

		if (IsDisabled())
		{
			m_overHandle = false;
			m_handleSize = m_troughSize;
			m_handleY = 0;
			return;
		}

		float handleSizeFactor = m_troughSize / float(m_wContainer.m_autoScrollHeight);
		if (handleSizeFactor < 0.05)
			handleSizeFactor = 0.05;
		m_handleSize = int(handleSizeFactor * m_troughSize);

		if (input.Forward.Pressed && m_hovering)
			OnMouseDown(mousePos);

		if (input.Forward.Down)
		{
			if (m_overHandle)
			{
				int moveHandleY = int(mousePos.y - m_troughOffset - m_overHandleY);
				if (moveHandleY < 0)
					moveHandleY = 0;
				else if (moveHandleY > m_troughSize - m_handleSize)
					moveHandleY = m_troughSize - m_handleSize;

				float setFactor = moveHandleY / float(max(1, m_troughSize - m_handleSize));
				m_wContainer.m_autoScrollValue = int(setFactor * (m_wContainer.m_autoScrollHeight - m_wContainer.m_height));
			}

			int scrollSpeed = 3;
			if (m_buttonUpPressed)
			{
				m_wContainer.m_autoScrollValue -= scrollSpeed;
				m_wContainer.TestAutoscrollLimit();
			}
			else if (m_buttonDownPressed)
			{
				m_wContainer.m_autoScrollValue += scrollSpeed;
				m_wContainer.TestAutoscrollLimit();
			}
		}
		else
		{
			m_overHandle = false;
			m_buttonUpPressed = false;
			m_buttonDownPressed = false;
		}

		float posFactor = m_wContainer.m_autoScrollValue / float(m_wContainer.m_autoScrollHeight - m_wContainer.m_height);
		if (posFactor < 0)
			posFactor = 0;
		else if (posFactor > 1)
			posFactor = 1;

		m_handleY = int(posFactor * (m_troughSize - m_handleSize));

		m_buttonUpHover = (m_hovering && mousePos.y < m_troughOffset);
		m_buttonDownHover = (m_hovering && mousePos.y > m_height - m_troughOffset);
		m_handleHover = (m_overHandle || (m_hovering && mousePos.y > m_troughOffset + m_handleY && mousePos.y < m_troughOffset + m_handleY + m_handleSize));
	}

	bool IsDisabled()
	{
		if (m_wContainer is null)
			return true;
		return m_wContainer.m_autoScrollHeight <= m_wContainer.m_height;
	}

	void DrawAt(SpriteBatch& sb, vec2 pos, Sprite@ sprite)
	{
		if (sprite is null)
			return;
		vec4 frame = sprite.GetFrame(g_menuTime);
		sb.DrawSprite(sprite.GetTexture2D(), vec4(pos.x, pos.y, frame.z, frame.w), frame);
	}

	void Fill(SpriteBatch& sb, vec4 rect, vec4 color)
	{
		sb.DrawSprite(null, rect, rect, color);
	}

	void DoDraw(SpriteBatch& sb, vec2 pos) override
	{
		if (m_wContainer is null)
			return;

		bool disabled = IsDisabled();
		if (m_hideOnFull && disabled)
			return;

		// Button up
		if (m_spriteButtonUp !is null)
		{
			if (disabled)
				DrawAt(sb, pos, m_spriteButtonUpDisabled);
			else if (m_buttonUpPressed)
				DrawAt(sb, pos, m_spriteButtonUpPressed);
			else if (m_buttonUpHover)
				DrawAt(sb, pos, m_spriteButtonUpHover);
			else
				DrawAt(sb, pos, m_spriteButtonUp);
		}
		else
			Fill(sb, vec4(pos.x, pos.y, m_width, m_buttonsSize), m_buttonUpHover ? m_colorButtonsHover : m_colorButtons);

		// Button down
		if (m_spriteButtonDown !is null)
		{
			vec2 buttonPos = pos + vec2(0, m_height - m_buttonsSize);
			if (disabled)
				DrawAt(sb, buttonPos, m_spriteButtonDownDisabled);
			else if (m_buttonDownPressed)
				DrawAt(sb, buttonPos, m_spriteButtonDownPressed);
			else if (m_buttonDownHover)
				DrawAt(sb, buttonPos, m_spriteButtonDownHover);
			else
				DrawAt(sb, buttonPos, m_spriteButtonDown);
		}
		else
			Fill(sb, vec4(pos.x, pos.y + m_height - m_buttonsSize, m_width, m_buttonsSize), m_buttonDownHover ? m_colorButtonsHover : m_colorButtons);

		// Trough (HoH1 wrapped its 1-pixel middle; stretched is the same picture)
		if (m_spriteTroughTop !is null)
		{
			Sprite@ spriteTop = disabled ? m_spriteTroughDisabledTop : m_spriteTroughTop;
			Sprite@ spriteMiddle = disabled ? m_spriteTroughDisabledMiddle : m_spriteTroughMiddle;
			Sprite@ spriteBottom = disabled ? m_spriteTroughDisabledBottom : m_spriteTroughBottom;

			int offsetDiff = m_troughOffset - m_buttonsSize;
			int span = m_troughSize + offsetDiff * 2;
			DrawAt(sb, pos + vec2(0, m_buttonsSize), spriteTop);
			DrawAt(sb, pos + vec2(0, m_buttonsSize + span - spriteBottom.GetHeight()), spriteBottom);
			int middle = span - spriteTop.GetHeight() - spriteBottom.GetHeight();
			if (middle > 0)
				sb.DrawSprite(spriteMiddle.GetTexture2D(),
					vec4(pos.x, pos.y + m_buttonsSize + spriteTop.GetHeight(), spriteMiddle.GetWidth(), middle),
					spriteMiddle.GetFrame(g_menuTime));
		}
		else
			Fill(sb, vec4(pos.x, pos.y + m_troughOffset, m_width, m_troughSize), m_colorTrough);

		// Handle
		if (!disabled)
		{
			vec4 handleRect = vec4(pos.x, pos.y + m_troughOffset + m_handleY, m_width, m_handleSize);
			if (m_spriteHandle !is null)
			{
				Texture2D@ texture = m_spriteHandle.GetTexture2D();

				vec4 spriteFrame = m_spriteHandle.GetFrame(g_menuTime);
				if (m_overHandle)
					spriteFrame = m_spriteHandlePressed.GetFrame(g_menuTime);
				else if (m_handleHover)
					spriteFrame = m_spriteHandleHover.GetFrame(g_menuTime);

				int widthDiff = int(handleRect.z - spriteFrame.z);
				handleRect.x += widthDiff / 2;
				handleRect.z -= widthDiff;

				int bh = m_handleBorder;

				sb.DrawSprite(texture, vec4(handleRect.x, handleRect.y, handleRect.z, bh), vec4(spriteFrame.x, spriteFrame.y, spriteFrame.z, bh));
				sb.DrawSprite(texture, handleRect + vec4(0, bh, 0, -bh * 2), spriteFrame + vec4(0, bh, 0, -bh * 2));
				sb.DrawSprite(texture, vec4(handleRect.x, handleRect.y + handleRect.w - bh, handleRect.z, bh), vec4(spriteFrame.x, spriteFrame.y + spriteFrame.w - bh, spriteFrame.z, bh));
			}
			else
				Fill(sb, handleRect, m_handleHover ? m_colorHandleHover : m_colorHandle);
		}
	}
}

ref@ LoadHoH1ScrollbarWidget(WidgetLoadingContext &ctx)
{
	HoH1ScrollbarWidget@ w = HoH1ScrollbarWidget();
	w.Load(ctx);
	return w;
}

namespace HWPCampaignHooks
{
	[Hook]
	void LoadWidgetProducers(GUIBuilder@ builder)
	{
		builder.AddWidgetProducer("hoh1-scrollrect", LoadHoH1ScrollableRectWidget);
		builder.AddWidgetProducer("hoh1-scrollbar", LoadHoH1ScrollbarWidget);
	}
}

// the gambler a bet was placed with (HoH1 kept it on the record by floor number): a
// floor's dealer gambles once, then shows what it gave; a new floor's is a new script
WorldScript::OpenInterface@ g_hoh1DealerUsed;
Item::Trinket@ g_hoh1DealerReward;

// HoH1's points per item quality; HoH1 had no cursed, quest or unique items, so those
// trinkets can't be bet
int HoH1DealerPoints(Item::Quality q)
{
	switch (q)
	{
		case Item::Quality::Common: return 1;
		case Item::Quality::Uncommon: return 3;
		case Item::Quality::Rare: return 7;
		case Item::Quality::Epic: return 12;
		case Item::Quality::Legendary: return 24;
	}
	return 0;
}

const array<Item::Quality> HOH1_DEALER_QUALITIES = {
	Item::Quality::Common, Item::Quality::Uncommon, Item::Quality::Rare,
	Item::Quality::Epic, Item::Quality::Legendary
};

// HoH1 set a widget's tooltip strings on the widget; HoH2 keeps them in a WidgetTooltip,
// which a clone shares with its template, so each widget gets its own ("" title: none)
void HoH1SetTooltip(Widget@ w, const string &in title, const string &in text)
{
	if (title == "" && text == "")
	{
		@w.m_tooltip = null;
		return;
	}
	WidgetTooltip@ t = WidgetTooltip();
	t.m_tooltipTitle = title;
	t.m_tooltipText = text;
	@w.m_tooltip = t;
}

// HoH1's SetActorItemOnGui: icon, tooltip, attuned plus, set and quality dots
void HoH1SetTrinketOnGui(PlayerRecord@ record, Widget@ wItem, Item::Trinket@ item)
{
	HoH1SetTooltip(wItem, "\\c" + Item::QualityColorString(item.m_quality) + utf8string(item.GetName()).toUpper().plain(),
		item.GetDescription(record));

	auto wIcon = cast<SpriteWidget>(wItem.GetWidgetById("item-icon"));
	if (wIcon !is null)
		wIcon.SetSprite(item.GetIcon());

	auto wAttuned = wItem.GetWidgetById("item-attuned");
	if (wAttuned !is null && record.attunedTrinkets.findByRef(item) != -1)
		wAttuned.m_visible = true;

	auto wSet = cast<SpriteWidget>(wItem.GetWidgetById("item-set"));
	if (wSet !is null && item.m_set !is null)
	{
		wSet.m_visible = true;
		wSet.m_color = ParseColorRGBA("#ffc800FF");
	}

	auto wQuality = cast<SpriteWidget>(wItem.GetWidgetById("item-quality"));
	if (wQuality !is null && item.m_quality != Item::Quality::Common)
	{
		wQuality.m_visible = true;
		wQuality.m_color = Item::QualityColor(item.m_quality);
	}
}

// ItemDealer: tick some trinkets, roll; they're gone and one random trinket comes back,
// its quality drawn from HoH1's tweak/itemdealer.sval row for the points bet
class HoH1ItemDealer : ScriptWidgetHost
{
	Widget@ m_wItemList;
	Widget@ m_wItemTemplate;
	Widget@ m_wQualityList;
	Widget@ m_wQualityTemplate;
	ScalableSpriteButtonWidget@ m_wGamble;
	RectWidget@ m_wFinalItem;

	array<Item::Trinket@> m_listed;

	HoH1ItemDealer(SValue& params)
	{
		super();
	}

	void Initialize(bool loaded) override
	{
		@m_wItemList = m_widget.GetWidgetById("list-items");
		@m_wItemTemplate = m_widget.GetWidgetById("template-item");
		@m_wQualityList = m_widget.GetWidgetById("list-qualities");
		@m_wQualityTemplate = m_widget.GetWidgetById("template-quality");
		@m_wGamble = cast<ScalableSpriteButtonWidget>(m_widget.GetWidgetById("gamble"));
		@m_wFinalItem = cast<RectWidget>(m_widget.GetWidgetById("final-item"));
		if (m_wItemList is null || m_wItemTemplate is null || m_wQualityList is null
			|| m_wQualityTemplate is null || m_wGamble is null || m_wFinalItem is null)
		{
			PrintError("HoH1ItemDealer: the item dealer's gui is missing a widget");
			return;
		}

		if (m_script !is null && m_script is g_hoh1DealerUsed && g_hoh1DealerReward !is null)
		{
			ReloadItemList(false);
			ShowFinalItem(g_hoh1DealerReward);
		}
		else
			ReloadItemList();

		UpdateButton();

		PauseGame(true, true);
	}

	bool ShouldFreezeControls() override { return true; }
	bool ShouldDisplayCursor() override { return true; }
	bool ShouldSaveExistance() override { return false; }

	void UpdateButton()
	{
		int numSelected = 0;
		for (uint i = 0; i < m_wItemList.m_children.length(); i++)
		{
			auto wItem = cast<CheckBoxWidget>(m_wItemList.m_children[i]);
			if (wItem !is null && wItem.IsChecked())
				numSelected++;
		}

		bool done = m_script !is null && m_script is g_hoh1DealerUsed;
		m_wGamble.m_enabled = !done && numSelected > 0;
		if (!done)
		{
			HoH1SetTooltip(m_wGamble, Resources::GetString(".hoh1.itemdealer.tooltip.title"), numSelected == 1
				? Resources::GetString(".hoh1.itemdealer.tooltip.single")
				: Resources::GetString(".hoh1.itemdealer.tooltip.plural", { { "num", numSelected } }));
		}

		array<Item::Quality> qualities;
		auto svReward = GetReward(GetCurrentPoints());
		if (svReward !is null)
		{
			auto arr = GetParamArray(UnitPtr(), svReward, "qualities");
			for (uint i = 0; i < arr.length(); i++)
				qualities.insertLast(Item::ParseQuality(arr[i].GetString()));
		}

		m_wQualityList.ClearChildren();
		for (uint i = 0; i < HOH1_DEALER_QUALITIES.length(); i++)
		{
			auto quality = HOH1_DEALER_QUALITIES[i];
			string name = Item::QualityToString(quality);

			int num = 0;
			for (uint j = 0; j < qualities.length(); j++)
			{
				if (qualities[j] == quality)
					num++;
			}
			float ratio = qualities.length() > 0 ? num / float(qualities.length()) : 0.0f;

			auto wNew = m_wQualityTemplate.Clone();
			wNew.SetID("");
			wNew.m_visible = true;
			HoH1SetTooltip(wNew, "\\c" + Item::QualityColorString(quality) + Resources::GetString(".item.quality." + name), "");

			auto wQuality = cast<SpriteWidget>(wNew.GetWidgetById("quality"));
			if (wQuality !is null)
				wQuality.SetSprite("quality-" + name);

			auto wPercentage = cast<TextWidget>(wNew.GetWidgetById("percentage"));
			if (wPercentage !is null)
			{
				wPercentage.m_color = Item::QualityColor(quality);
				wPercentage.SetText(ceil(ratio * 100.0f) + "%");
			}

			m_wQualityList.AddChild(wNew);
		}
	}

	void ShowFinalItem(Item::Trinket@ item)
	{
		HoH1SetTrinketOnGui(GetLocalPlayerRecord(), m_wFinalItem, item);
		vec4 c = Item::QualityColor(item.m_quality);
		m_wFinalItem.m_color = vec4(c.x * 0.35f, c.y * 0.35f, c.z * 0.35f, 1.0f);

		m_wGamble.m_enabled = false;
		HoH1SetTooltip(m_wGamble, "", "");
	}

	void ReloadItemList(bool enabled = true)
	{
		m_wItemList.ClearChildren();
		m_listed.removeRange(0, m_listed.length());

		auto record = GetLocalPlayerRecord();
		if (record is null || record.trinketInventory is null)
			return;

		auto items = record.trinketInventory.m_items;
		for (uint i = 0; i < items.length(); i++)
		{
			auto item = items[i];
			if (item is null || HoH1DealerPoints(item.m_quality) == 0)
				continue;

			auto wNew = cast<CheckBoxWidget>(m_wItemTemplate.Clone());
			if (wNew is null)
				continue;
			wNew.SetID("");
			wNew.m_visible = true;
			wNew.m_value = "" + m_listed.length();
			wNew.m_enabled = enabled;
			HoH1SetTrinketOnGui(record, wNew, item);
			m_wItemList.AddChild(wNew);
			m_listed.insertLast(item);
		}

		m_wGamble.m_enabled = false;
	}

	array<Item::Trinket@> Selected()
	{
		array<Item::Trinket@> ret;
		for (uint i = 0; i < m_wItemList.m_children.length(); i++)
		{
			auto wItem = cast<CheckBoxWidget>(m_wItemList.m_children[i]);
			if (wItem is null || !wItem.IsChecked())
				continue;
			int index = parseInt(wItem.m_value);
			if (index >= 0 && index < int(m_listed.length()))
				ret.insertLast(m_listed[index]);
		}
		return ret;
	}

	int GetCurrentPoints()
	{
		int points = 0;
		auto sel = Selected();
		for (uint i = 0; i < sel.length(); i++)
			points += HoH1DealerPoints(sel[i].m_quality);
		return points;
	}

	// HoH1: the first row whose min-points the bet is over (the last row has none)
	SValue@ GetReward(int points)
	{
		auto sval = Resources::GetSValue("hoh1/tweak/itemdealer.sval");
		if (sval is null)
			return null;
		auto rows = sval.GetArray();
		for (uint i = 0; i < rows.length(); i++)
		{
			if (points > GetParamInt(UnitPtr(), rows[i], "min-points", false))
				return rows[i];
		}
		return null;
	}

	// what a gamble would do, for GameLab: the bet, the points and the row's qualities
	string Describe()
	{
		string qs;
		auto svReward = GetReward(GetCurrentPoints());
		if (svReward !is null)
		{
			auto arr = GetParamArray(UnitPtr(), svReward, "qualities");
			for (uint i = 0; i < arr.length(); i++)
				qs += (i > 0 ? "," : "") + arr[i].GetString();
		}
		return "listed " + m_listed.length() + " selected " + Selected().length() + " points " + GetCurrentPoints() + " qualities " + qs;
	}

	void CommitGamble()
	{
		auto record = GetLocalPlayerRecord();
		if (record is null || record.actor is null)
		{
			PrintError("Player is dead!");
			return;
		}
		if (m_script !is null && m_script is g_hoh1DealerUsed)
			return;

		auto svReward = GetReward(GetCurrentPoints());
		auto sel = Selected();
		if (sel.length() == 0 || svReward is null)
			return;

		for (uint i = 0; i < sel.length(); i++)
			record.trinketInventory.Remove(sel[i]);

		array<Item::Quality> qualities;
		auto arr = GetParamArray(UnitPtr(), svReward, "qualities");
		for (uint i = 0; i < arr.length(); i++)
			qualities.insertLast(Item::ParseQuality(arr[i].GetString()));

		auto newItem = Item::GetRandomTrinket(record, qualities[randi(qualities.length())]);
		record.GiveItem(newItem);
		record.trinketInventory.RefreshPlayerModifiers();

		@g_hoh1DealerUsed = m_script;
		@g_hoh1DealerReward = newItem;

		ReloadItemList(false);
		ShowFinalItem(newItem);
	}

	void Stop() override
	{
		ScriptWidgetHost::Stop();
		PauseGame(false, true);
	}

	void OnFunc(Widget@ sender, const string &in name) override
	{
		if (name == "close")
			Stop();
		else if (name == "gamble")
			CommitGamble();
		else if (name == "item-checked")
			UpdateButton();
	}
}

// EndOfGame: HoH1's closing story after Thundersnow; CONTINUE ends the mission as won,
// the way HoH2 ends one after its last floor (MissionManager::NextLevel past the end),
// and the stats button opens HoH2's player menu
class HoH1EndOfGame : ScriptWidgetHost
{
	HoH1EndOfGame(SValue& params)
	{
		super();
	}

	void Initialize(bool loaded) override
	{
		auto wButtonTown = cast<ScalableSpriteButtonWidget>(m_widget.GetWidgetById("button-town"));
		if (wButtonTown !is null)
			wButtonTown.m_enabled = Network::IsServer();
	}

	bool ShouldFreezeControls() override { return true; }
	bool ShouldDisplayCursor() override { return true; }

	// HoH1's window can't be closed: CONTINUE is the way out
	void Stop() override
	{
	}

	void OnFunc(Widget@ sender, const string &in name) override
	{
		if (name == "town")
		{
			if (Network::IsServer())
				MissionManager::AbortMission(MissionManager::MissionState::Succeeded);
		}
		else if (name == "stats")
		{
			auto gm = cast<HWR2GameMode>(g_gameMode);
			if (gm !is null)
				gm.TogglePlayerMenu();
		}
	}
}
