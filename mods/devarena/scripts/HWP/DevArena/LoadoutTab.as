// The dock's Loadout tab (docs/devarena/SPEC.md, "Loadout"). The dock widens to 45% for it.
//
// Favorites on top: one click applies. Below, two columns when the dock is wide enough
// (1080p and 1440p at the default ui scale), else stacked:
//   browser: a search field, class chips, subclass chips, then one row per preset of that
//            subclass (or every preset the search matches): compare tick, apply, favorite star.
//   sheet:   the live record: class, level, free stars and stat points (red when overspent),
//            attributes, gear per slot, trinkets, skills and combos. A value that differs from
//            the applied preset is marked * in yellow. Level, attributes, skills and combos
//            have [-] [+] steppers. Revert re-applies the preset; Save logs the build as a variant.
//
// Every change goes through Loadout.as's queue, so it lands on a frame with no cast. Saves and
// favorites are log lines (the game cannot write files):
//   [HWP:devarena] loadout-variant {"id":"<preset>+e1","from":"<preset>","level":12,"rows":[...]}
//   [HWP:devarena] loadout-favorites ["ranger_nature/mid",...]
// and `python tools/make_presets.py --import-log` folds them into tools/devarena/presets_hand.json.
namespace HWP
{
namespace DevArena
{
	const float LOADOUT_FRAC = 0.45f;
	const float TWO_COLUMNS_W = 300;     // UI units: below this the browser and sheet stack
	const int COMPARE_MAX = 2;

	string g_lClass;                     // browser: base class picked
	string g_lSub;                       // browser: subclass picked
	string g_lSearch;
	array<string> g_compare;             // ticked presets (to the golem bench)
	array<string> g_favorites;           // from the preset file, then this session's changes
	int g_variantSaves;

	string BaseClass(const string &in cls)
	{
		int us = cls.findFirst("_");
		return us < 0 ? cls : cls.substr(0, us);
	}

	void ToggleFavorite(const string &in id)
	{
		int at = g_favorites.find(id);
		if (at >= 0)
			g_favorites.removeAt(at);
		else
			g_favorites.insertLast(id);
		array<string> q;
		for (uint i = 0; i < g_favorites.length(); i++)
			q.insertLast(GameLab::Quote(g_favorites[i]));
		HWP::Log("devarena", "loadout-favorites " + GameLab::RawArray(q));
		g_lastAction = (at >= 0 ? "unfavorite " : "favorite ") + id;
	}

	void ToggleCompare(const string &in id)
	{
		int at = g_compare.find(id);
		if (at >= 0)
			g_compare.removeAt(at);
		else
		{
			if (int(g_compare.length()) >= COMPARE_MAX)
				g_compare.removeAt(0);
			g_compare.insertLast(id);
		}
	}

	array<string>@ Row(const string &in verb, const string &in id, const string &in n)
	{
		array<string> r = { verb, id };
		if (n != "")
			r.insertLast(n);
		return r;
	}

	dictionary@ Picked(PlayerRecord@ rec, bool combo)
	{
		if (combo)
			return rec.pickedComboSkills;
		return rec.pickedSkills;
	}

	// the live record as preset rows, in the file's order (stats, skills, combos, gear, trinkets)
	array<array<string>>@ RecordRows()
	{
		array<array<string>> rows;
		auto plr = LocalPlayer();
		if (plr is null)
			return rows;
		auto rec = plr.m_record;
		array<string> attrs = { "str", "dex", "int", "foc", "vit" };
		for (uint i = 0; i < attrs.length(); i++)
			if (GetStat(rec, attrs[i]) > 0)
				rows.insertLast(Row("stat", attrs[i], "" + GetStat(rec, attrs[i])));
		for (int c = 0; c < 2; c++)
		{
			dictionary@ d = Picked(rec, c == 1);
			auto keys = d.getKeys();
			keys.sortAsc();
			for (uint i = 0; i < keys.length(); i++)
			{
				int n = 0;
				d.get(keys[i], n);
				if (n > 0)
					rows.insertLast(Row(c == 0 ? "skill" : "combo", keys[i], "" + n));
			}
		}
		for (uint i = 0; i < rec.equipped.m_items.length(); i++)
		{
			auto it = cast<Equipment::Item>(rec.equipped.m_items[i]);
			if (it !is null)
				rows.insertLast(Row("equip", it.baseItem.m_id, ""));
		}
		for (uint i = 0; i < rec.trinketInventory.m_items.length(); i++)
			rows.insertLast(Row("trinket", rec.trinketInventory.m_items[i].m_id, ""));
		return rows;
	}

	void SaveVariant()
	{
		auto p = FindPreset(g_preset);
		auto plr = LocalPlayer();
		if (p is null || plr is null)
		{
			g_lastError = "save: apply a preset first";
			return;
		}
		g_variantSaves++;
		string vid = p.id + "+e" + g_variantSaves;
		auto rows = RecordRows();
		array<string> rs;
		for (uint i = 0; i < rows.length(); i++)
		{
			array<string> cells;
			for (uint k = 0; k < rows[i].length(); k++)
				cells.insertLast(GameLab::Quote(rows[i][k]));
			rs.insertLast(GameLab::RawArray(cells));
		}
		HWP::Log("devarena", "loadout-variant {\"id\":" + GameLab::Quote(vid) + ",\"from\":" + GameLab::Quote(p.id)
			+ ",\"level\":" + plr.m_record.level + ",\"rows\":" + GameLab::RawArray(rs) + "}");
		g_lastAction = "saved " + vid + " (import-log to keep)";
	}

	// the preset's value for (verb, id), "" when it has none
	string PresetValue(Preset@ p, const string &in verb, const string &in id)
	{
		if (p is null)
			return "";
		for (uint i = 0; i < p.rows.length(); i++)
			if (p.rows[i][0] == verb && p.rows[i][1] == id)
				return p.rows[i].length() > 2 ? p.rows[i][2] : id;
		return "";
	}

	float LayoutLoadout(Ui@ ui, float x, float y, float w)
	{
		float row = RowH();
		if (g_presets.length() == 0)
		{
			ui.Text(x, y, "no presets: python tools/make_presets.py", COL_ERR);
			return y + row;
		}

		// favorites
		ui.Text(x, y + 1, "Fav", COL_HEAD);
		float fx = x + ui.TextW("Fav") + 5;
		if (g_favorites.length() == 0)
			ui.Text(fx, y + 1, "none: * a preset", COL_DIM);
		for (uint i = 0; i < g_favorites.length(); i++)
		{
			string id = g_favorites[i];
			float fw = min(ui.TextW(id) + 5, w);
			if (fx > x && fx + fw > x + w)
			{
				fx = x;
				y += row + 2;
			}
			if (ui.Button("fav|" + id, vec4(fx, y, fw, row), Short(ui, id, fw - 4), g_preset == id ? COL_ON : COL_BUTTON))
				QueuePreset(id);
			fx += fw + 2;
		}
		y += row + PAD;

		bool two = w >= TWO_COLUMNS_W;
		float cw = two ? floor((w - PAD) * 0.5f) : w;
		float yb = LayoutBrowser(ui, x, y, cw);
		float sx = two ? x + cw + PAD : x;
		float ys = LayoutSheet(ui, sx, two ? y : yb + PAD, cw);
		if (two)
			ui.Fill(vec4(x + cw + PAD * 0.5f, y, 1, max(yb, ys) - y), COL_DIM);
		return max(yb, ys);
	}

	// wrapped chips; returns the new y and sets `clicked` on a click ("" if none)
	float Chips(Ui@ ui, const string &in prefix, array<string>@ ids, float x, float y, float w, const string &in current, string &out clicked)
	{
		clicked = "";
		float row = RowH();
		float cx = x;
		for (uint i = 0; i < ids.length(); i++)
		{
			float bw = min(ui.TextW(ids[i]) + 5, w);
			if (cx > x && cx + bw > x + w)
			{
				cx = x;
				y += row + 2;
			}
			if (ui.Button(prefix + ids[i], vec4(cx, y, bw, row), Short(ui, ids[i], bw - 4), current == ids[i] ? COL_ON : COL_BUTTON))
				clicked = ids[i];
			cx += bw + 2;
		}
		return y + row + PAD;
	}

	float LayoutBrowser(Ui@ ui, float x, float y, float w)
	{
		float row = RowH();
		Field(ui, "lsearch", vec4(x, y, w, row), g_lSearch);
		if (g_lSearch == "" && !(g_typing && g_editId == "lsearch"))
			ui.Text(x + 3, y + 1, "search presets", COL_DIM);
		y += row + 2;

		if (g_lClass == "" && g_preset != "")
			g_lClass = BaseClass(FindPreset(g_preset).cls);
		array<string> bases, subs;
		for (uint i = 0; i < g_presets.length(); i++)
		{
			string b = BaseClass(g_presets[i].cls);
			if (bases.find(b) < 0)
				bases.insertLast(b);
			if (b == g_lClass && subs.find(g_presets[i].cls) < 0)
				subs.insertLast(g_presets[i].cls);
		}
		if (g_lClass == "")
			g_lClass = bases[0];
		string clicked;
		y = Chips(ui, "lclass|", bases, x, y, w, g_lClass, clicked);
		if (clicked != "" && clicked != g_lClass)
		{
			g_lClass = clicked;
			g_lSub = "";
		}
		if (subs.length() > 0 && subs.find(g_lSub) < 0)
			g_lSub = (g_preset != "" && subs.find(FindPreset(g_preset).cls) >= 0) ? FindPreset(g_preset).cls : subs[0];
		// subclass chips without the class prefix: "nature" for ranger_nature
		array<string> shortIds;
		for (uint i = 0; i < subs.length(); i++)
			shortIds.insertLast(subs[i].substr(g_lClass.length() + 1));
		string sub = g_lSub.length() > g_lClass.length() ? g_lSub.substr(g_lClass.length() + 1) : "";
		if (subs.length() > 0)
		{
			y = Chips(ui, "lsub|", shortIds, x, y, w, sub, clicked);
			g_lSub = g_lClass + "_" + (clicked != "" ? clicked : sub);
		}

		// preset rows
		int shown = 0;
		float tw = ui.TextW("[x]") + 4;
		float sw = ui.TextW("*") + 6;
		for (uint i = 0; i < g_presets.length(); i++)
		{
			auto p = g_presets[i];
			if (g_lSearch != "" ? p.id.findFirst(g_lSearch) < 0 : p.cls != g_lSub)
				continue;
			shown++;
			bool ticked = g_compare.find(p.id) >= 0;
			if (ui.Button("cmp|" + p.id, vec4(x, y, tw, row), ticked ? "[x]" : "[ ]", ticked ? COL_ON : COL_BUTTON))
				ToggleCompare(p.id);
			string label = g_lSearch != "" ? p.id : p.id.substr(p.cls.length() + 1);
			label += "  L" + p.level;
			float pw = w - tw - sw - 4;
			if (ui.Button("preset|" + p.id, vec4(x + tw + 2, y, pw, row), Short(ui, label, pw - 4), g_preset == p.id ? COL_ON : COL_BUTTON))
				QueuePreset(p.id);
			bool fav = g_favorites.find(p.id) >= 0;
			if (ui.Button("star|" + p.id, vec4(x + w - sw, y, sw, row), fav ? "*" : ".", COL_BUTTON, fav ? COL_HEAD : COL_DIM))
				ToggleFavorite(p.id);
			y += row + 1;
		}
		if (shown == 0)
		{
			ui.Text(x, y, "no match", COL_DIM);
			y += row;
		}
		y += PAD;
		string cmp = g_compare.length() == 0 ? "compare: tick two" : "compare: " + join(g_compare, " vs ");
		ui.Text(x, y, Short(ui, cmp, w), g_compare.length() == COMPARE_MAX ? COL_TEXT : COL_DIM);
		y += row;
		if (g_compare.length() == 2)
		{
			// the two ticked loadouts as the bench's A and B (Bench.as, HP3)
			if (ui.Button("lbench", vec4(x, y, w, row), "Bench these on the golem"))
			{
				g_benchSource = 1;
				g_tab = "bench";
				g_scroll = 0;
				g_lastAction = "bench: " + join(g_compare, " vs ");
			}
			y += row;
		}
		return y;
	}

	// "label  value" with a [-] [+] pair at the right; returns -1 / +1 on a click
	int Stepper(Ui@ ui, const string &in id, float x, float y, float w, const string &in label, const string &in value, bool changed)
	{
		float row = RowH();
		float bw = ui.TextW("+") + 6;
		ui.Text(x, y + 1, Short(ui, label, w - bw * 2 - ui.TextW(value) - 12), COL_TEXT);
		string v = changed ? value + "*" : value;
		ui.Text(x + w - bw * 2 - 4 - ui.TextW(v), y + 1, v, changed ? COL_HEAD : COL_TEXT);
		int d = 0;
		if (ui.Button(id + "|-", vec4(x + w - bw * 2 - 2, y, bw, row), "-"))
			d = -1;
		if (ui.Button(id + "|+", vec4(x + w - bw, y, bw, row), "+"))
			d = 1;
		return d;
	}

	float LayoutSheet(Ui@ ui, float x, float y, float w)
	{
		float row = RowH();
		auto plr = LocalPlayer();
		if (plr is null)
		{
			ui.Text(x, y, "no player", COL_DIM);
			return y + row;
		}
		auto rec = plr.m_record;
		auto p = FindPreset(g_preset);

		ui.Text(x, y, Short(ui, g_preset == "" ? "no preset applied" : g_preset, w), COL_HEAD);
		y += row;
		int stars = rec.GetFreeSkillPoints();
		int pts = rec.GetPlaceableStatPoints();
		ui.Text(x, y, Short(ui, rec.playerClass.m_id, w * 0.5f), COL_DIM);
		string budget = "stars " + stars + "  pts " + pts;
		ui.Text(x + w - ui.TextW(budget), y, budget, stars < 0 || pts < 0 ? COL_ERR : COL_DIM);
		y += row + 1;

		float bw = (w - 2) * 0.5f;
		if (ui.Button("lrevert", vec4(x, y, bw, row), "Revert", COL_BUTTON, p is null ? COL_DIM : COL_TEXT) && p !is null)
			QueuePreset(p.id);
		if (ui.Button("lsave", vec4(x + bw + 2, y, bw, row), "Save variant", COL_BUTTON, p is null ? COL_DIM : COL_TEXT))
			SaveVariant();
		y += row + PAD;

		int d = Stepper(ui, "llevel", x, y, w, "level", "" + rec.level, p !is null && p.level != rec.level);
		if (d != 0)
			QueueOp("level", "", d);
		y += row + 1;

		ui.Text(x, y, "ATTRIBUTES", COL_HEAD);
		y += row;
		array<string> attrs = { "str", "dex", "int", "foc", "vit" };
		for (uint i = 0; i < attrs.length(); i++)
		{
			string want = PresetValue(p, "stat", attrs[i]);
			int got = GetStat(rec, attrs[i]);
			bool changed = p !is null && (want == "" ? got != 0 : parseInt(want) != got);
			d = Stepper(ui, "lstat|" + attrs[i], x, y, w, attrs[i], "" + got, changed);
			if (d != 0)
				QueueOp("stat", attrs[i], d);
			y += row + 1;
		}

		ui.Text(x, y, "SKILLS", COL_HEAD);
		y += row;
		for (int c = 0; c < 2; c++)
		{
			string verb = c == 0 ? "skill" : "combo";
			array<string> ids;
			dictionary@ picked = Picked(rec, c == 1);
			auto keys = picked.getKeys();
			for (uint i = 0; i < keys.length(); i++)
				ids.insertLast(keys[i]);
			if (c == 0)
			{
				auto bar = TuneSkills();
				for (uint i = 0; i < bar.length(); i++)
					if (ids.find(bar[i]) < 0 && FindDef(bar[i]) !is null && FindDef(bar[i]).m_startingLevel == 0)
						ids.insertLast(bar[i]);
			}
			for (uint i = 0; p !is null && i < p.rows.length(); i++)
				if (p.rows[i][0] == verb && ids.find(p.rows[i][1]) < 0)
					ids.insertLast(p.rows[i][1]);
			ids.sortAsc();
			for (uint i = 0; i < ids.length(); i++)
			{
				int n = 0;
				picked.get(ids[i], n);
				string want = PresetValue(p, verb, ids[i]);
				bool changed = p !is null && (want == "" ? n != 0 : parseInt(want) != n);
				string label = ids[i];
				string cls = rec.playerClass.m_id;
				if (label.findFirst(cls + "_") == 0)
					label = label.substr(cls.length() + 1);
				d = Stepper(ui, "l" + verb + "|" + ids[i], x, y, w, (c == 1 ? "c " : "") + label, "" + n, changed);
				if (d != 0)
					QueueOp(verb, ids[i], d);
				y += row + 1;
			}
		}

		ui.Text(x, y, "GEAR  (reqs off)", COL_HEAD);
		y += row;
		array<string> slots = { "main", "off", "head", "chest", "feet", "hands", "back" };
		for (uint i = 0; i < rec.equipped.m_items.length() && i < slots.length(); i++)
		{
			auto it = cast<Equipment::Item>(rec.equipped.m_items[i]);
			string id = it is null ? "-" : it.baseItem.m_id;
			bool changed = p !is null && it !is null && PresetValue(p, "equip", id) == "";
			string q = it is null ? "" : " " + Item::QualityToString(it.quality) + " i" + it.itemLevel;
			string s = slots[i] + " " + id + (changed ? "*" : "");
			ui.Text(x, y, Short(ui, s, w - ui.TextW(q) - 2), changed ? COL_HEAD : (it is null ? COL_DIM : COL_TEXT));
			ui.Text(x + w - ui.TextW(q), y, q, COL_DIM);
			y += row;
		}

		auto inv = rec.trinketInventory.m_items;
		ui.Text(x, y, "TRINKETS " + inv.length(), COL_HEAD);
		y += row;
		for (uint i = 0; i < inv.length(); i++)
		{
			bool changed = p !is null && PresetValue(p, "trinket", inv[i].m_id) == "";
			ui.Text(x, y, Short(ui, inv[i].m_id + (changed ? "*" : ""), w), changed ? COL_HEAD : COL_TEXT);
			y += row;
		}
		return y;
	}
}
}
