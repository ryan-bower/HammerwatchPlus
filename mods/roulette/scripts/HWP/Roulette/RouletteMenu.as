// The roulette table's window (gui/hwp_roulette.gui): the interact of the wheel on the
// tavern table (doodads/hwp/hwp_roulette_wheel.unit). It does not pause the game: the
// lobby's round runs on while it is open (HWP::Roulette, RouletteTable.as).
//
// hwp-roulette-board: the European layout, drawn in code. The zero on the left, the
// numbers 3 to a column (3 on top), the 2-to-1 column boxes on the right, the dozens and
// the six even-money boxes below. A click inside a number bets on it; a click near a line
// or a corner bets on the numbers that line or corner touches, the way chips sit on a real
// table (KeyAt). Hovering shows what a click would cover. Mouse only.
// hwp-roulette-strip: the wheel's pockets in their real order, scrolling to the number
// while the ball runs.
namespace HWP
{
	namespace Roulette
	{
		// the board, in pixels
		const float Z = 20;    // the zero's width
		const float CW = 22;   // a number's cell
		const float CH = 18;
		const float E = 4;     // how near a line a click counts as on it
		const float P = 20;    // a pocket's width on the strip
		const array<string> OUTSIDE = { "low", "even", "red", "black", "odd", "high" };

		int g_chip = 0;          // the chip the board places, an index in CHIPS
		string g_hoverKey;       // the bet under the mouse on the board
		string g_notice;         // what the last press said (a refused bet)
		int g_spinFrom = 0;      // the strip's pocket when the spin began (OnState)

		vec4 CellRect(int n)
		{
			if (n == 0)
				return vec4(0, 0, Z, 3 * CH);
			int c = (n - 1) / 3, r = 2 - (n - 1) % 3;
			return vec4(Z + c * CW, r * CH, CW, CH);
		}

		vec2 CellMid(int n)
		{
			vec4 r = CellRect(n);
			return vec2(r.x + r.z / 2, r.y + r.w / 2);
		}

		// the bet a click at (x, y) on the board places; "" off the board
		string KeyAt(float x, float y)
		{
			float gx = x - Z;
			if (x < 0 || y < 0 || gx >= 13 * CW || y >= 5 * CH)
				return "";
			if (y < 3 * CH + E && gx > -E && gx < 12 * CW + E)
			{
				int c = clamp(int(floor(gx / CW)), 0, 11);
				int r = clamp(int(floor(y / CH)), 0, 2);
				float fx = gx - c * CW, fy = y - r * CH;
				int vb = fx < E ? c : (fx > CW - E ? c + 1 : -1);   // the line left of column vb
				int hb = fy < E ? r : (fy > CH - E ? r + 1 : -1);   // the line above row hb
				if (vb == 12)
					vb = -1;   // the column boxes' line: the number itself
				if (hb == 0)
					hb = -1;   // the top edge: the number itself
				int n = 3 * c + 3 - r;
				if (vb < 0 && hb < 0)
					return "s:" + n;
				if (vb < 0)
				{
					if (hb == 3)
						return "st:" + (3 * c + 1);
					int a = 3 * c + 3 - hb;
					return "sp:" + a + "-" + (a + 1);
				}
				if (hb < 0)
				{
					if (vb == 0)
						return "sp:0-" + (3 - r);
					int a = 3 * (vb - 1) + 3 - r;
					return "sp:" + a + "-" + (a + 3);
				}
				if (vb == 0)
					return hb == 3 ? "f4" : (hb == 1 ? "t:0-2-3" : "t:0-1-2");
				if (hb == 3)
					return "sl:" + (3 * (vb - 1) + 1);
				return "c:" + (3 * (vb - 1) + 3 - hb);
			}
			if (y < 3 * CH)
				return gx < 0 ? "s:0" : "col:" + (3 - int(y / CH));
			if (gx < 0 || gx >= 12 * CW)
				return "";
			if (y < 4 * CH)
				return "d:" + (int(gx / (4 * CW)) + 1);
			return OUTSIDE[clamp(int(gx / (2 * CW)), 0, 5)];
		}

		// the box of an outside bet (the column, dozen and even-money boxes)
		bool BoxOf(const string &in key, vec4 &out box)
		{
			if (key.substr(0, 4) == "col:")
			{
				int k = parseInt(key.substr(4));
				box = vec4(Z + 12 * CW, (3 - k) * CH, CW, CH);
				return true;
			}
			if (key.substr(0, 2) == "d:")
			{
				int k = parseInt(key.substr(2));
				box = vec4(Z + (k - 1) * 4 * CW, 3 * CH, 4 * CW, CH);
				return true;
			}
			int i = OUTSIDE.find(key);
			if (i >= 0)
			{
				box = vec4(Z + i * 2 * CW, 4 * CH, 2 * CW, CH);
				return true;
			}
			return false;
		}

		// where a bet's chip sits on the board
		vec2 Anchor(const string &in key)
		{
			vec4 box;
			if (BoxOf(key, box))
				return vec2(box.x + box.z / 2, box.y + box.w / 2);
			auto bet = Get(key);
			if (bet is null)
				return vec2();
			string kind = key.substr(0, key.findFirst(":"));
			if (key == "f4")
				return vec2(Z, 3 * CH);
			if (kind == "t")
				return vec2(Z, key == "t:0-2-3" ? CH : 2 * CH);
			if (kind == "st")
				return vec2(CellMid(bet.nums[0]).x, 3 * CH);
			if (kind == "sl")
				return vec2(CellRect(bet.nums[0]).x + CW, 3 * CH);
			if (kind == "sp" && bet.nums[0] == 0)
				return vec2(Z, CellMid(bet.nums[1]).y);
			vec2 sum;
			for (uint i = 0; i < bet.nums.length(); i++)
				sum += CellMid(bet.nums[i]);
			return sum / float(bet.nums.length());
		}

		vec4 NumColor(int n)
		{
			if (n == 0)
				return vec4(0.10f, 0.50f, 0.22f, 1);
			return IsRed(n) ? vec4(0.70f, 0.10f, 0.09f, 1) : vec4(0.09f, 0.09f, 0.10f, 1);
		}

		string NumColorName(int n)
		{
			return Resources::GetString(n == 0 ? ".hwp.roulette.green" : IsRed(n) ? ".hwp.roulette.red" : ".hwp.roulette.black");
		}

		vec4 ChipColor(int stake)
		{
			if (stake >= CHIPS[3])
				return vec4(0.95f, 0.78f, 0.25f, 1);
			if (stake >= CHIPS[2])
				return vec4(0.25f, 0.45f, 0.95f, 1);
			if (stake >= CHIPS[1])
				return vec4(0.90f, 0.25f, 0.20f, 1);
			return vec4(0.92f, 0.92f, 0.88f, 1);
		}

		string Short(int gold)
		{
			if (gold >= 1000000 && gold % 1000000 == 0)
				return "" + (gold / 1000000) + "M";
			if (gold >= 1000 && gold % 1000 == 0)
				return "" + (gold / 1000) + "K";
			return "" + gold;
		}

		void Frame(SpriteBatch& sb, vec4 r, vec4 color, float w = 1)
		{
			sb.FillRectangle(vec4(r.x, r.y, r.z, w), color);
			sb.FillRectangle(vec4(r.x, r.y + r.w - w, r.z, w), color);
			sb.FillRectangle(vec4(r.x, r.y, w, r.w), color);
			sb.FillRectangle(vec4(r.x + r.z - w, r.y, w, r.w), color);
		}
	}
}

class HWPRouletteShop : AShopContent
{
	HWPRouletteShop() {}
	HWPRouletteShop(UnitPtr u, SValue& params) { super(u, params); }

	bool CanInteract(PlayerRecord@ player) override { return HWP::Roulette::g_enabled; }

	AWindowObject@ MakeShopWindow(GUIBuilder@ guiBuilder) override
	{
		@m_window = HWPRouletteMenu(guiBuilder, this);
		return m_window;
	}

	string GetName() override { return "roulette"; }
	UsableIcon GetIcon() override { return UsableIcon::Generic; }
}

class HWPRouletteMenu : AWindowObject
{
	HWPRouletteShop@ m_shop;
	TextWidget@ m_phase;
	TextWidget@ m_hover;
	TextWidget@ m_gold;
	TextWidget@ m_mine;
	TextWidget@ m_bonus;
	TextWidget@ m_last;
	TextWidget@ m_history;
	TextWidget@ m_lobby;
	ScalableSpriteButtonWidget@ m_clear;
	ScalableSpriteButtonWidget@ m_spin;
	array<ScalableSpriteButtonWidget@> m_chips;
	int m_refresh = 0;

	HWPRouletteMenu(GUIBuilder@ b, HWPRouletteShop@ shop)
	{
		super(b, "gui/hwp_roulette.gui");
		@m_shop = shop;
		@m_phase = cast<TextWidget>(m_widget.GetWidgetById("phase"));
		@m_hover = cast<TextWidget>(m_widget.GetWidgetById("hover"));
		@m_gold = cast<TextWidget>(m_widget.GetWidgetById("gold"));
		@m_mine = cast<TextWidget>(m_widget.GetWidgetById("mine"));
		@m_bonus = cast<TextWidget>(m_widget.GetWidgetById("bonus"));
		@m_last = cast<TextWidget>(m_widget.GetWidgetById("last"));
		@m_history = cast<TextWidget>(m_widget.GetWidgetById("history"));
		@m_lobby = cast<TextWidget>(m_widget.GetWidgetById("lobby"));
		@m_clear = cast<ScalableSpriteButtonWidget>(m_widget.GetWidgetById("clear-btn"));
		@m_spin = cast<ScalableSpriteButtonWidget>(m_widget.GetWidgetById("spin-btn"));
		for (uint i = 0; i < HWP::Roulette::CHIPS.length(); i++)
		{
			auto btn = cast<ScalableSpriteButtonWidget>(m_widget.GetWidgetById("chip-" + i));
			if (btn is null)
				continue;
			btn.SetText(HWP::Roulette::Short(HWP::Roulette::CHIPS[i]));
			m_chips.insertLast(btn);
		}
		HWP::Roulette::g_notice = "";
		if (!Network::IsServer())
			HWP::Net::Request("roulette.hello");
		Refresh();
	}

	void OnFunc(Widget@ sender, const string &in name) override
	{
		if (name == "close")
		{
			m_closing = true;
			m_manager.CloseWindow(this);
			return;
		}
		HWP::Roulette::g_notice = "";
		auto parse = name.split(" ");
		if (parse.length() == 2 && parse[0] == "chip")
			HWP::Roulette::g_chip = clamp(parseInt(parse[1]), 0, int(HWP::Roulette::CHIPS.length()) - 1);
		else if (name == "clear")
			HWP::Roulette::Clear();
		else if (name == "spin" && HWP::Roulette::CanSpinNow())
			HWP::Net::Request("roulette.spin");
		Refresh();
	}

	bool Update(int ms, GameInput& gameInput, MenuInput& menuInput) override
	{
		bool r = AWindowObject::Update(ms, gameInput, menuInput);
		m_refresh -= ms;
		if (m_refresh <= 0)
			Refresh();
		return r;
	}

	void Set(TextWidget@ w, const string &in text)
	{
		if (w !is null && w.m_str != text)
			w.SetText(text);
	}

	void Refresh()
	{
		m_refresh = 100;
		int s = (HWP::Roulette::g_ms + 999) / 1000;
		int num = HWP::Roulette::g_result;
		string phase;
		switch (HWP::Roulette::g_phase)
		{
			case HWP::Roulette::Phase::Betting: phase = Resources::GetString(".hwp.roulette.phase.betting", { { "s", s } }); break;
			case HWP::Roulette::Phase::Spinning: phase = Resources::GetString(".hwp.roulette.phase.spinning"); break;
			case HWP::Roulette::Phase::Result: phase = Resources::GetString(".hwp.roulette.phase.result", { { "num", num }, { "colour", HWP::Roulette::NumColorName(num) } }); break;
			default: phase = Resources::GetString(".hwp.roulette.phase.closed");
		}
		Set(m_phase, phase);

		int chip = HWP::Roulette::CHIPS[HWP::Roulette::g_chip];
		auto bet = HWP::Roulette::Get(HWP::Roulette::g_hoverKey);
		if (!HWP::Roulette::g_notice.isEmpty())
			Set(m_hover, "\\cff8080" + HWP::Roulette::g_notice);
		else if (bet !is null)
			Set(m_hover, Resources::GetString(".hwp.roulette.hover", { { "name", bet.name }, { "odds", bet.odds },
				{ "chip", HWP::Roulette::Short(chip) }, { "pay", HWP::Roulette::Payout(chip, bet.odds) },
				{ "mine", HWP::Roulette::MyStake(bet.key) } }));
		else
			Set(m_hover, Resources::GetString(".hwp.roulette.hover_none"));

		Set(m_gold, Resources::GetString(".hwp.roulette.gold", { { "gold", HWP::Roulette::Gold() } }));
		Set(m_mine, Resources::GetString(".hwp.roulette.mine", { { "total", HWP::Roulette::MyTotal() },
			{ "max", HWP::Roulette::Short(HWP::Roulette::MaxStake()) } }));
		Set(m_bonus, HWP::Roulette::BonusText());
		Set(m_last, HWP::Roulette::g_lastText);
		string hist;
		for (uint i = 0; i < HWP::Roulette::g_history.length(); i++)
		{
			int n = HWP::Roulette::g_history[i];
			hist += (i > 0 ? " " : "") + (n == 0 ? "\\c40d070" : HWP::Roulette::IsRed(n) ? "\\cff5050" : "\\cc0c0c0") + n + "\\d";
		}
		Set(m_history, Resources::GetString(".hwp.roulette.history", { { "list", hist.isEmpty() ? "-" : hist } }));
		Set(m_lobby, Resources::GetString(".hwp.roulette.lobby", { { "players", HWP::Roulette::g_betPlayers },
			{ "staked", HWP::Roulette::g_staked } }));

		for (uint i = 0; i < m_chips.length(); i++)
		{
			m_chips[i].SetChecked(int(i) == HWP::Roulette::g_chip);
			m_chips[i].m_enabled = HWP::Roulette::Gold() >= HWP::Roulette::CHIPS[i];
		}
		if (m_clear !is null)
			m_clear.m_enabled = HWP::Roulette::CanBet() && HWP::Roulette::MyTotal() > 0;
		if (m_spin !is null)
		{
			m_spin.m_visible = HWP::Roulette::Lobby() <= 1;
			m_spin.m_enabled = HWP::Roulette::CanSpinNow();
		}
	}
}

class HWPRouletteBoard : AInteractableWidget
{
	array<BitmapString@> m_labels;   // 0-36, then LABELS
	BitmapFont@ m_font;
	int m_blink = 0;

	HWPRouletteBoard() { super(); }

	Widget@ Clone() override
	{
		HWPRouletteBoard@ w = HWPRouletteBoard();
		CloneInto(w);
		return w;
	}

	void Load(WidgetLoadingContext &ctx) override
	{
		AInteractableWidget::Load(ctx);
		@m_font = Resources::GetBitmapFont("gui/fonts/arial11.fnt");
	}

	BitmapString@ Label(uint i)
	{
		if (m_labels.length() == 0 && m_font !is null)
		{
			for (int n = 0; n <= 36; n++)
				m_labels.insertLast(m_font.BuildText("" + n));
			array<string> words = { ".hwp.roulette.board.col", ".hwp.roulette.board.d1", ".hwp.roulette.board.d2",
				".hwp.roulette.board.d3", ".hwp.roulette.board.low", ".hwp.roulette.board.even",
				".hwp.roulette.board.odd", ".hwp.roulette.board.high" };
			for (uint k = 0; k < words.length(); k++)
				m_labels.insertLast(m_font.BuildText(Resources::GetString(words[k])));
		}
		return i < m_labels.length() ? m_labels[i] : null;
	}

	void Centered(SpriteBatch& sb, vec2 pos, vec4 box, uint label)
	{
		auto t = Label(label);
		if (t !is null)
			sb.DrawString(pos + vec2(int(box.x + (box.z - t.GetWidth()) / 2), int(box.y + (box.w - t.GetHeight()) / 2 + 1)), t);
	}

	vec2 Mouse()
	{
		return GetGameModeMousePosition() / g_gameMode.m_wndScale - m_origin;
	}

	void Update(int dt) override
	{
		m_blink += dt;
		if (m_hovering)
		{
			vec2 m = Mouse();
			HWP::Roulette::g_hoverKey = HWP::Roulette::KeyAt(m.x, m.y);
		}
		Widget::Update(dt);
	}

	void Leave() override
	{
		HWP::Roulette::g_hoverKey = "";
		AInteractableWidget::Leave();
	}

	void ClickUp(bool usingMouse, vec2 mousePos) override
	{
		AInteractableWidget::ClickUp(usingMouse, mousePos);
		vec2 m = Mouse();
		string key = HWP::Roulette::KeyAt(m.x, m.y);
		if (key.isEmpty())
			return;
		if (HWP::Roulette::Place(key, HWP::Roulette::CHIPS[HWP::Roulette::g_chip]))
			HWP::Roulette::g_notice = "";
		else
			HWP::Roulette::g_notice = Resources::GetString(HWP::Roulette::g_why);
	}

	void DoDraw(SpriteBatch& sb, vec2 pos) override
	{
		const vec4 felt = vec4(0.07f, 0.33f, 0.16f, 1);
		const vec4 line = vec4(0.85f, 0.82f, 0.70f, 1);
		sb.FillRectangle(vec4(pos.x, pos.y, m_width, m_height), felt);

		// the numbers and the zero
		for (int n = 0; n <= 36; n++)
		{
			vec4 r = HWP::Roulette::CellRect(n);
			sb.FillRectangle(vec4(pos.x + r.x + 1, pos.y + r.y + 1, r.z - 2, r.w - 2), HWP::Roulette::NumColor(n));
			Centered(sb, pos, r, n);
		}
		// the column, dozen and even-money boxes
		for (int k = 1; k <= 3; k++)
		{
			vec4 box;
			HWP::Roulette::BoxOf("col:" + k, box);
			Centered(sb, pos, box, 37);
			HWP::Roulette::BoxOf("d:" + k, box);
			Centered(sb, pos, box, 37 + k);
		}
		array<uint> outLabel = { 41, 42, 0, 0, 43, 44 };
		for (uint i = 0; i < HWP::Roulette::OUTSIDE.length(); i++)
		{
			vec4 box;
			HWP::Roulette::BoxOf(HWP::Roulette::OUTSIDE[i], box);
			if (i == 2 || i == 3)
				sb.FillRectangle(vec4(pos.x + box.x + box.z / 2 - 7, pos.y + box.y + 4, 14, box.w - 8),
					HWP::Roulette::NumColor(i == 2 ? 1 : 2));
			else
				Centered(sb, pos, box, outLabel[i]);
		}
		// the lines
		for (int c = 0; c <= 12; c++)
			sb.FillRectangle(vec4(pos.x + HWP::Roulette::Z + c * HWP::Roulette::CW, pos.y, 1, 3 * HWP::Roulette::CH), line);
		for (int r = 0; r <= 5; r++)
		{
			float x0 = r <= 3 ? 0 : HWP::Roulette::Z;
			float w = r <= 2 ? m_width : 12 * HWP::Roulette::CW + (r == 3 ? HWP::Roulette::Z + HWP::Roulette::CW : 0);
			sb.FillRectangle(vec4(pos.x + x0, pos.y + r * HWP::Roulette::CH - (r == 5 ? 1 : 0), w, 1), line);
		}
		for (int k = 0; k <= 3; k++)
			sb.FillRectangle(vec4(pos.x + HWP::Roulette::Z + k * 4 * HWP::Roulette::CW, pos.y + 3 * HWP::Roulette::CH, 1, HWP::Roulette::CH), line);
		for (int k = 0; k <= 6; k++)
			sb.FillRectangle(vec4(pos.x + HWP::Roulette::Z + k * 2 * HWP::Roulette::CW - (k == 6 ? 1 : 0), pos.y + 4 * HWP::Roulette::CH, 1, HWP::Roulette::CH), line);
		sb.FillRectangle(vec4(pos.x, pos.y, 1, 3 * HWP::Roulette::CH), line);
		sb.FillRectangle(vec4(pos.x + m_width - 1, pos.y, 1, 3 * HWP::Roulette::CH), line);

		// what the mouse would bet on
		auto hover = HWP::Roulette::Get(HWP::Roulette::g_hoverKey);
		if (hover !is null && HWP::Roulette::CanBet())
		{
			vec4 box;
			if (HWP::Roulette::BoxOf(hover.key, box))
				sb.FillRectangle(vec4(pos.x + box.x + 1, pos.y + box.y + 1, box.z - 2, box.w - 2), vec4(1, 1, 1, 0.25f));
			for (uint i = 0; i < hover.nums.length(); i++)
			{
				vec4 r = HWP::Roulette::CellRect(hover.nums[i]);
				sb.FillRectangle(vec4(pos.x + r.x + 1, pos.y + r.y + 1, r.z - 2, r.w - 2), vec4(1, 1, 1, 0.30f));
			}
		}

		// the number that came up
		if (HWP::Roulette::g_phase == HWP::Roulette::Phase::Result && HWP::Roulette::g_result >= 0 && (m_blink / 300) % 2 == 0)
		{
			vec4 r = HWP::Roulette::CellRect(HWP::Roulette::g_result);
			HWP::Roulette::Frame(sb, vec4(pos.x + r.x, pos.y + r.y, r.z + 1, r.w + 1), vec4(1, 0.85f, 0.2f, 1), 2);
		}

		// the local player's chips
		for (uint i = 0; i < HWP::Roulette::g_myKeys.length(); i++)
		{
			if (HWP::Roulette::g_myRound != HWP::Roulette::g_round)
				break;
			vec2 a = pos + HWP::Roulette::Anchor(HWP::Roulette::g_myKeys[i]);
			vec4 col = HWP::Roulette::ChipColor(HWP::Roulette::g_myStakes[i]);
			vec4 rim = vec4(col.x * 0.5f, col.y * 0.5f, col.z * 0.5f, 1);
			sb.FillRectangle(vec4(int(a.x) - 4, int(a.y) - 3, 9, 7), rim);
			sb.FillRectangle(vec4(int(a.x) - 3, int(a.y) - 4, 7, 9), rim);
			sb.FillRectangle(vec4(int(a.x) - 3, int(a.y) - 2, 7, 5), col);
			sb.FillRectangle(vec4(int(a.x) - 2, int(a.y) - 3, 5, 7), col);
		}

		// no bets now
		if (!HWP::Roulette::CanBet())
			sb.FillRectangle(vec4(pos.x, pos.y, m_width, m_height), vec4(0, 0, 0, 0.30f));
	}
}

class HWPRouletteStrip : Widget
{
	array<BitmapString@> m_nums;
	BitmapFont@ m_font;

	HWPRouletteStrip() { super(); }

	Widget@ Clone() override
	{
		HWPRouletteStrip@ w = HWPRouletteStrip();
		CloneInto(w);
		return w;
	}

	void Load(WidgetLoadingContext &ctx) override
	{
		LoadWidthHeight(ctx, false);
		Widget::Load(ctx);
		@m_font = Resources::GetBitmapFont("gui/fonts/arial11.fnt");
	}

	// the pocket under the marker: still on the last number, and easing out over a few
	// turns of the wheel to this round's number while the ball runs
	float Position()
	{
		int last = HWP::Roulette::g_history.length() > 0 ? HWP::Roulette::WHEEL.find(HWP::Roulette::g_history[0]) : 0;
		if (HWP::Roulette::g_phase != HWP::Roulette::Phase::Spinning || HWP::Roulette::g_result < 0)
			return float(last);
		float t = clamp(1.0f - float(HWP::Roulette::g_ms) / float(HWP::Roulette::SPIN_MS), 0.0f, 1.0f);
		float ease = 1.0f - (1.0f - t) * (1.0f - t) * (1.0f - t);
		int from = HWP::Roulette::g_spinFrom;
		int to = HWP::Roulette::WHEEL.find(HWP::Roulette::g_result);
		int steps = 3 * HWP::Roulette::NUMBERS + ((to - from) % HWP::Roulette::NUMBERS + HWP::Roulette::NUMBERS) % HWP::Roulette::NUMBERS;
		return float(from) + float(steps) * ease;
	}

	void DoDraw(SpriteBatch& sb, vec2 pos) override
	{
		if (m_font !is null && m_nums.length() == 0)
		{
			for (int n = 0; n <= 36; n++)
				m_nums.insertLast(m_font.BuildText("" + n));
		}
		sb.FillRectangle(vec4(pos.x, pos.y, m_width, m_height), vec4(0.24f, 0.14f, 0.07f, 1));
		float at = Position();
		float mid = m_width / 2.0f;
		int first = int(floor(at - mid / HWP::Roulette::P)) - 1, last = int(ceil(at + mid / HWP::Roulette::P)) + 1;
		for (int k = first; k <= last; k++)
		{
			int n = HWP::Roulette::WHEEL[(k % HWP::Roulette::NUMBERS + HWP::Roulette::NUMBERS) % HWP::Roulette::NUMBERS];
			float x0 = mid + (float(k) - at) * HWP::Roulette::P - HWP::Roulette::P / 2;
			float x1 = x0 + HWP::Roulette::P;
			float cx0 = max(x0 + 1, 1.0f), cx1 = min(x1 - 1, float(m_width) - 1);
			if (cx1 <= cx0)
				continue;
			sb.FillRectangle(vec4(pos.x + cx0, pos.y + 3, cx1 - cx0, m_height - 6), HWP::Roulette::NumColor(n));
			if (x0 >= 0 && x1 <= m_width && n < int(m_nums.length()))
			{
				auto t = m_nums[n];
				sb.DrawString(pos + vec2(int(x0 + (HWP::Roulette::P - t.GetWidth()) / 2), int((m_height - t.GetHeight()) / 2 + 1)), t);
			}
		}
		// the marker
		vec4 gold = vec4(1, 0.85f, 0.2f, 1);
		sb.FillRectangle(vec4(pos.x + mid - HWP::Roulette::P / 2, pos.y, HWP::Roulette::P, 2), gold);
		sb.FillRectangle(vec4(pos.x + mid - HWP::Roulette::P / 2, pos.y + m_height - 2, HWP::Roulette::P, 2), gold);
		HWP::Roulette::Frame(sb, vec4(pos.x, pos.y, m_width, m_height), vec4(0.5f, 0.32f, 0.15f, 1));
	}
}

ref@ LoadHWPRouletteBoard(WidgetLoadingContext &ctx)
{
	HWPRouletteBoard@ w = HWPRouletteBoard();
	w.Load(ctx);
	return w;
}

ref@ LoadHWPRouletteStrip(WidgetLoadingContext &ctx)
{
	HWPRouletteStrip@ w = HWPRouletteStrip();
	w.Load(ctx);
	return w;
}

namespace HWPRoulette
{
	[Hook]
	void LoadWidgetProducers(GUIBuilder@ builder)
	{
		builder.AddWidgetProducer("hwp-roulette-board", LoadHWPRouletteBoard);
		builder.AddWidgetProducer("hwp-roulette-strip", LoadHWPRouletteStrip);
	}
}
