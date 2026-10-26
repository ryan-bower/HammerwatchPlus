// Interact class of doodads/hwp/laststats_board.unit and its window: every
// player's last run on one page. Each stat is a row with one horizontal bar per
// player (the player's colour, labelled with the value, scaled to the biggest
// value of that stat); the search field filters the rows by stat name as you
// type (func-edit "search"). Rows are built once from the union of the party's
// snapshots and only shown / hidden by the filter, so typing never rebuilds the
// list under the field's focus.
class HWPLastStatsBoard : AShopContent
{
	HWPLastStatsBoard() {}
	HWPLastStatsBoard(UnitPtr u, SValue& params)
	{
		super(u, params);
	}

	bool CanInteract(PlayerRecord@ player) override { return true; }

	AWindowObject@ MakeShopWindow(GUIBuilder@ guiBuilder) override
	{
		@m_window = HWPLastStatsMenu(guiBuilder, this);
		return m_window;
	}

	string GetName() override { return "hwp_laststats_board"; }

	void Save(SValueBuilder& builder) override { }
	void Load(SValue@ sval) override { }
}

namespace HWP
{
	namespace LastStats
	{
		// one stat across the party: the row and its per-player values
		class StatRow
		{
			string cat;
			string title;
			string key;          // cat + "|" + title (the snapshots carry no stat id before 2026-10-25)
			array<int> values;   // per player index, 0 when the player has no such line
			array<string> texts; // the pre-formatted value per player, "" when none
			Widget@ widget;
			bool shown;
		}

		HWPLastStatsMenu@ g_openMenu; // the board window while it is open (hwp laststats board)
		const int BAR_MAX = 150;      // the widest bar, in widget units
		const int ROW_H = 11;         // a bar line
	}
}

class HWPLastStatsMenu : AWindowObject
{
	array<HWP::LastStats::StatRow@> m_rowsData;
	array<Widget@> m_headers;   // category header + separator widgets, hidden when no row of theirs shows
	array<string> m_headerCats;
	array<string> m_players;
	int m_shown = 0;

	Widget@ m_statGroup;
	Widget@ m_empty;
	Widget@ m_nomatch;
	Widget@ m_legend;
	TextWidget@ m_subtitle;
	TextWidget@ m_legendTemplate;
	TextWidget@ m_categoryTemplate;
	Widget@ m_separatorTemplate;
	Widget@ m_rowTemplate;
	TextInputWidget@ m_search;
	TextWidget@ m_searchHint;
	string m_query;

	HWPLastStatsMenu(GUIBuilder@ b, HWPLastStatsBoard@ board)
	{
		super(b, "gui/hwp_laststats.gui");
		PauseGame(true, true);

		@m_statGroup = m_widget.GetWidgetById("stat-group");
		@m_empty = m_widget.GetWidgetById("empty");
		@m_nomatch = m_widget.GetWidgetById("nomatch");
		@m_legend = m_widget.GetWidgetById("legend");
		@m_subtitle = cast<TextWidget>(m_widget.GetWidgetById("subtitle"));
		@m_legendTemplate = cast<TextWidget>(m_widget.GetWidgetById("legend-template"));
		@m_categoryTemplate = cast<TextWidget>(m_widget.GetWidgetById("stat-category-template"));
		@m_separatorTemplate = m_widget.GetWidgetById("stat-separator");
		@m_rowTemplate = m_widget.GetWidgetById("stat-row-template");
		@m_search = cast<TextInputWidget>(m_widget.GetWidgetById("search"));
		@m_searchHint = cast<TextWidget>(m_widget.GetWidgetById("search-hint"));
		// the console key's char opens the console; it is never part of a search
		if (m_search !is null)
		{
			m_search.m_forbiddenCharacters.insertLast("`");
			m_search.m_forbiddenCharacters.insertLast("~");
		}

		@HWP::LastStats::g_openMenu = this;
		Build();
		ApplyFilter();
	}

	// ---- the rows: union of every snapshot's stats, category order kept ------

	HWP::LastStats::StatRow@ RowFor(const string &in cat, const string &in title)
	{
		string key = cat + "|" + title;
		for (uint i = 0; i < m_rowsData.length(); i++)
		{
			if (m_rowsData[i].key == key)
				return m_rowsData[i];
		}
		return null;
	}

	int ColumnOf(const string &in player)
	{
		for (uint i = 0; i < m_players.length(); i++)
			if (m_players[i] == player)
				return int(i);
		return -1;
	}

	void Build()
	{
		m_statGroup.ClearChildren();
		m_legend.ClearChildren();
		m_rowsData.removeRange(0, m_rowsData.length());
		m_headers.removeRange(0, m_headers.length());
		m_headerCats.removeRange(0, m_headerCats.length());
		m_players.removeRange(0, m_players.length());

		auto@ party = HWP::LastStats::g_party;
		bool has = party.length() > 0;
		m_empty.m_visible = !has;
		if (!has)
		{
			m_subtitle.SetText("");
			return;
		}

		// the local player first, then the others newest first
		array<SValue@> order;
		auto local = GetLocalPlayerRecord();
		for (uint i = 0; i < party.length(); i++)
		{
			if (local !is null && HWP::SV::Str(party[i], "player") == local.GetName())
				order.insertAt(0, party[i]);
			else
				order.insertLast(party[i]);
		}

		// legend: a coloured name per player, with the run's result
		int x = 0;
		for (uint p = 0; p < order.length(); p++)
		{
			auto snap = order[p];
			string name = HWP::SV::Str(snap, "player");
			m_players.insertLast(name);
			auto entry = cast<TextWidget>(m_legendTemplate.Clone());
			entry.SetID("legend-" + p);
			entry.m_visible = true;
			entry.m_offset = vec2(x, 0);
			entry.SetText(name + " (" + HWP::LastStats::StateName(HWP::SV::Int(snap, "state")) + ")");
			entry.SetColor(PlayerColor(HWP::SV::Int(snap, "peer", 0)));
			m_legend.AddChild(entry);
			x += 85;
		}
		m_subtitle.SetText(Resources::GetString(".hwp.laststats.subtitle", {
			{ "mission", HWP::SV::Str(order[0], "mission") },
			{ "state", Resources::GetString(".hwp.laststats.players", { { "count", "" + order.length() } }) } }));

		// the union of stats, in each snapshot's (StatDef) order, grouped by category
		for (uint p = 0; p < order.length(); p++)
		{
			auto linesV = HWP::SV::Field(order[p], "lines");
			if (linesV is null)
				continue;
			auto lines = linesV.GetArray();
			if (lines is null)
				continue;
			for (uint i = 0; i < lines.length(); i++)
			{
				auto line = lines[i];
				string cat = HWP::SV::Str(line, "cat");
				string title = HWP::SV::Str(line, "title");
				auto row = RowFor(cat, title);
				if (row is null)
				{
					HWP::LastStats::StatRow r;
					r.cat = cat;
					r.title = title;
					r.key = cat + "|" + title;
					for (uint k = 0; k < order.length(); k++)
					{
						r.values.insertLast(0);
						r.texts.insertLast("");
					}
					@row = r;
					// after the last row of its category, else at the end
					int at = -1;
					for (int j = int(m_rowsData.length()) - 1; j >= 0; j--)
					{
						if (m_rowsData[j].cat == cat)
						{
							at = j + 1;
							break;
						}
					}
					if (at < 0)
						m_rowsData.insertLast(r);
					else
						m_rowsData.insertAt(uint(at), r);
				}
				row.values[p] = HWP::SV::Int(line, "value", 0);
				row.texts[p] = HWP::SV::Str(line, "text");
			}
		}

		// widgets, in row order with a header per category
		string lastCat = "";
		for (uint i = 0; i < m_rowsData.length(); i++)
		{
			auto row = m_rowsData[i];
			if (row.cat != lastCat)
			{
				AddCategory(row.cat);
				lastCat = row.cat;
			}
			@row.widget = MakeRow(row, i);
			m_statGroup.AddChild(row.widget);
		}
	}

	vec4 PlayerColor(int peer)
	{
		return ParseColorRGBA("#" + GetPlayerColor(peer) + "ff");
	}

	void AddCategory(const string &in cat)
	{
		if (m_statGroup.m_children.length() > 0)
		{
			auto sep = m_separatorTemplate.Clone();
			sep.SetID("sep-" + cat);
			sep.m_visible = true;
			m_statGroup.AddChild(sep);
			m_headers.insertLast(sep);
			m_headerCats.insertLast(cat);
		}
		auto header = cast<TextWidget>(m_categoryTemplate.Clone());
		header.SetID("cat-" + cat);
		header.m_visible = true;
		string key = cat == "skill_dmg" ? ".hwp.laststats.category.skill_dmg" : ".menu.stats.cat." + cat;
		header.SetText(Resources::GetString(key));
		m_statGroup.AddChild(header);
		m_headers.insertLast(header);
		m_headerCats.insertLast(cat);
	}

	// a stat row: the title, then one bar line per player (name, bar, value)
	Widget@ MakeRow(HWP::LastStats::StatRow@ row, uint index)
	{
		auto w = m_rowTemplate.Clone();
		w.SetID("stat-" + index);
		w.m_visible = true;
		auto title = cast<TextWidget>(w.GetWidgetById("stat-title"));
		title.SetID("stat-title-" + index); // unique ids: gl wtext reads them
		title.SetText(row.title);
		w.GetWidgetById("stat-bg").m_visible = (index % 2) == 1;

		int maxVal = 0;
		for (uint p = 0; p < row.values.length(); p++)
			if (row.values[p] > maxVal)
				maxVal = row.values[p];

		auto barTemplate = w.GetWidgetById("bar-template");
		int y = 12;
		for (uint p = 0; p < m_players.length(); p++)
		{
			auto line = barTemplate.Clone();
			line.SetID("bar-" + index + "-" + p);
			line.m_visible = true;
			line.m_offset = vec2(0, y);
			y += HWP::LastStats::ROW_H;

			auto snapPeer = PeerOf(m_players[p]);
			auto name = cast<TextWidget>(line.GetWidgetById("bar-name"));
			name.SetID("bar-name-" + index + "-" + p);
			name.SetText(m_players[p]);
			name.SetColor(PlayerColor(snapPeer));

			int val = row.values[p];
			int width = 1;
			if (maxVal > 0 && val > 0)
				width = max(2, int(float(HWP::LastStats::BAR_MAX) * float(val) / float(maxVal) + 0.5f));
			auto bar = cast<RectWidget>(line.GetWidgetById("bar"));
			bar.m_width = width;
			bar.m_color = PlayerColor(snapPeer);
			bar.m_visible = val > 0;

			auto value = cast<TextWidget>(line.GetWidgetById("bar-value"));
			value.SetID("bar-value-" + index + "-" + p);
			value.m_offset = vec2(96 + width, 0);
			value.SetText(row.texts[p].isEmpty() ? "-" : row.texts[p]);
			w.AddChild(line);
		}
		w.m_height = y + 1;
		return w;
	}

	int PeerOf(const string &in player)
	{
		auto@ party = HWP::LastStats::g_party;
		for (uint i = 0; i < party.length(); i++)
			if (HWP::SV::Str(party[i], "player") == player)
				return HWP::SV::Int(party[i], "peer", 0);
		return 0;
	}

	// ---- search ------------------------------------------------------------

	bool Matches(HWP::LastStats::StatRow@ row)
	{
		if (m_query.isEmpty())
			return true;
		return row.title.toLower().findFirst(m_query) >= 0;
	}

	void SetQuery(const string &in text)
	{
		string q = text.toLower();
		while (q.length() > 0 && q.substr(q.length() - 1) == " ")
			q = q.substr(0, q.length() - 1);
		while (q.length() > 0 && q.substr(0, 1) == " ")
			q = q.substr(1);
		if (q == m_query)
			return;
		m_query = q;
		ApplyFilter();
	}

	void ApplyFilter()
	{
		m_shown = 0;
		array<string> shownCats;
		for (uint i = 0; i < m_rowsData.length(); i++)
		{
			auto row = m_rowsData[i];
			bool show = Matches(row);
			row.shown = show;
			if (row.widget !is null && row.widget.m_visible != show)
				row.widget.m_visible = show;
			if (show)
			{
				m_shown++;
				if (shownCats.find(row.cat) < 0)
					shownCats.insertLast(row.cat);
			}
		}
		// a category header (and the separator above it) only with a row of its own
		for (uint i = 0; i < m_headers.length(); i++)
		{
			bool show = shownCats.find(m_headerCats[i]) >= 0;
			if (m_headers[i].m_visible != show)
				m_headers[i].m_visible = show;
		}
		m_nomatch.m_visible = m_rowsData.length() > 0 && m_shown == 0;
		Invalidate();
		HWP::Log("laststats", "board: " + m_shown + " of " + m_rowsData.length() + " stats shown, "
			+ m_players.length() + " players, filter \"" + m_query + "\"");
	}

	// for "hwp laststats board": what the window shows right now
	string Status()
	{
		int bars = 0;
		for (uint i = 0; i < m_rowsData.length(); i++)
		{
			if (!m_rowsData[i].shown || m_rowsData[i].widget is null)
				continue;
			for (uint c = 0; c < m_rowsData[i].widget.m_children.length(); c++)
			{
				auto child = m_rowsData[i].widget.m_children[c];
				if (child.m_id.findFirst("bar-") == 0 && child.m_visible)
					bars++;
			}
		}
		string titles;
		int n = 0;
		for (uint i = 0; i < m_rowsData.length() && n < 12; i++)
		{
			if (!m_rowsData[i].shown)
				continue;
			titles += (n > 0 ? "; " : "") + m_rowsData[i].title;
			n++;
		}
		return "board open: " + m_shown + " of " + m_rowsData.length() + " stats, " + m_players.length()
			+ " players, " + bars + " bars, filter \"" + m_query + "\", typing " + (m_search !is null && m_search.m_typing ? "1" : "0")
			+ ", input \"" + (m_search is null ? "" : m_search.m_text.plain()) + "\", rows: " + titles;
	}

	bool Update(int ms, GameInput& gameInput, MenuInput& menuInput) override
	{
		if (m_searchHint !is null && m_search !is null)
		{
			bool empty = m_search.m_text.length() == 0 && !m_search.m_typing;
			if (m_searchHint.m_visible != empty)
				m_searchHint.m_visible = empty;
		}
		return AWindowObject::Update(ms, gameInput, menuInput);
	}

	void OnClose() override
	{
		if (HWP::LastStats::g_openMenu is this)
			@HWP::LastStats::g_openMenu = null;
		PauseGame(false, true);
	}

	void OnFunc(Widget@ sender, const string &in name) override
	{
		if (name == "close")
		{
			m_closing = true; // the NPC's IsDone() reads it; CloseWindow doesn't set it
			m_manager.CloseWindow(this);
		}
		else if (name == "search")
		{
			if (m_search !is null)
				SetQuery(m_search.m_text.plain());
		}
		else if (name == "search-clear")
		{
			if (m_search !is null)
				m_search.SetText("");
			SetQuery("");
		}
		else if (name.findFirst("search ") == 0)
		{
			// "search <text>" (gl func, a key-bound action): the same as typing it
			string text = name.substr(7);
			if (m_search !is null)
				m_search.SetText(text);
			SetQuery(text);
		}
	}
}
