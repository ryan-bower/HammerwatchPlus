// The HammerwatchPlus tab of the player menu: our settings, since the game's
// own Options menu runs in the menu script, which never loads mod scripts or
// mod gui files (GameLab probe-options-menu), and its keybind list is a fixed
// table in the exe. gui/playermenu/playermenu.gui adds the tab button and an
// hwp-options-hook widget that hands the PlayerMenu an HWPOptionsTab
// (gui/hwp/options.gui) on its first update.
//
// The list comes from HWP::Config (Config.as): a top section (packages.json
// settings_top), then one collapsible row per package with its modules' on/off
// switches and settings. An Option (key binds, presets) is registered by its
// module in the ctor (script globals reset every level) under the id its
// config names ({"option": "<id>"}, row "hwp-opt-<id>"); one no config lists
// goes in the top section, one not registered hides. Values are read every
// frame while the tab is open, so providers need no change calls.
namespace HWP
{
	namespace Options
	{
		class Option
		{
			string Title() { return ""; }
			string Value() { return ""; }
			// clicking the row's button: usually the next choice
			void Next() {}
		}

		// a keyboard key: clicking the button waits for the next key press
		class KeyOption : Option
		{
			int Scancode() { return 0; }
			void SetScancode(int scancode) {}
			string Value() override { return KeyName(Scancode()); }
		}

		dictionary g_options;
		// the ids of the packages open in the Plus tab (this level); not a dictionary of bools:
		// get(key, bool &out) copies its out temp back for a missing key too, so a package
		// nobody opened read as open
		array<string> g_open;

		void Register(const string &in id, Option@ option)
		{
			g_options.set(id, @option);
		}

		Option@ Get(const string &in id)
		{
			Option@ option;
			if (g_options.get(id, @option))
				return option;
			return null;
		}

		const int SC_ESCAPE = 41;
		const int SC_FIRST = 4;
		const int SC_LAST = 231;

		// SDL scancode names (USB HID usage ids), as the keys are printed
		string KeyName(int sc)
		{
			if (sc >= 4 && sc <= 29)
				return "ABCDEFGHIJKLMNOPQRSTUVWXYZ".substr(sc - 4, 1);
			if (sc >= 30 && sc <= 39)
				return "1234567890".substr(sc - 30, 1);
			if (sc >= 58 && sc <= 69)
				return "F" + (sc - 57);
			if (sc >= 89 && sc <= 98)
				return "Num " + "1234567890".substr(sc - 89, 1);
			switch (sc)
			{
				case 40: return "Enter";
				case 41: return "Esc";
				case 42: return "Backspace";
				case 43: return "Tab";
				case 44: return "Space";
				case 45: return "-";
				case 46: return "=";
				case 47: return "[";
				case 48: return "]";
				case 49: return "\\";
				case 51: return ";";
				case 52: return "'";
				case 53: return "`";
				case 54: return ",";
				case 55: return ".";
				case 56: return "/";
				case 57: return "Caps Lock";
				case 73: return "Insert";
				case 74: return "Home";
				case 75: return "Page Up";
				case 76: return "Delete";
				case 77: return "End";
				case 78: return "Page Down";
				case 79: return "Right";
				case 80: return "Left";
				case 81: return "Down";
				case 82: return "Up";
				case 224: return "Left Ctrl";
				case 225: return "Left Shift";
				case 226: return "Left Alt";
				case 228: return "Right Ctrl";
				case 229: return "Right Shift";
				case 230: return "Right Alt";
			}
			return "Key " + sc;
		}

		bool KeyDown(int sc) { return Platform::IsKeyDown(ControllerType::Keyboard, 0, sc); }

		// the first key held down, or -1
		int AnyKeyDown()
		{
			for (int sc = SC_FIRST; sc <= SC_LAST; sc++)
			{
				if (KeyDown(sc))
					return sc;
			}
			return -1;
		}

		// the HammerwatchPlus tab is the current tab of the open character menu
		// (a key a module polls should not fire while it is being set there)
		bool TabOpen()
		{
			auto gm = cast<BaseGameMode>(g_gameMode);
			if (gm is null || gm.m_windowManager is null)
				return false;
			for (uint i = 0; i < gm.m_windowManager.m_objects.length(); i++)
			{
				auto w = gm.m_windowManager.m_objects[i];
				if (cast<HWPKeyCaptureWindow>(w) !is null)
					return true;
				auto menu = cast<PlayerMenu>(w);
				if (menu !is null && menu.m_tabSystem.m_tabs.length() > 0
					&& cast<HWPOptionsTab>(menu.m_tabSystem.GetCurrentTab()) !is null)
					return true;
			}
			return false;
		}
	}
}

// Over the Plus tab while a KeyOption waits for its key. Only the top window
// gets input (WindowManager), so the menu underneath cannot switch tabs or
// close on the key being bound, and the character-menu toggle is refused
// while another window is on top. Esc is the game's menu back, which closes
// only this top window (Back): that cancels.
class HWPKeyCaptureWindow : AWindowObject
{
	HWPOptionsTab@ m_tab;
	string m_id;
	bool m_armed;      // every key was up since the capture started

	HWPKeyCaptureWindow(GUIBuilder@ b, HWPOptionsTab@ tab, const string &in id)
	{
		super(b, "gui/hwp/keycapture.gui");
		@m_tab = tab;
		m_id = id;
		auto opt = HWP::Options::Get(id);
		auto text = cast<TextWidget>(m_widget.GetWidgetById("text"));
		if (text !is null && opt !is null)
			text.SetText(Resources::GetString(".hwp.options.capture", { { "what", opt.Title() } }));
	}

	// no AWindowObject::Update: no navigation, and Esc must not close the menu
	bool Update(int ms, GameInput& gameInput, MenuInput& menuInput) override
	{
		IWidgetHoster::Update(ms);
		auto opt = cast<HWP::Options::KeyOption>(HWP::Options::Get(m_id));
		if (opt is null)
			return Done();
		int sc = HWP::Options::AnyKeyDown();
		if (!m_armed)
		{
			// the key that pressed the row's button (Enter) must come up first
			m_armed = sc < 0;
			return false;
		}
		if (sc < 0 || sc == HWP::Options::SC_ESCAPE)
			return false;
		opt.SetScancode(sc);
		HWP::Log("options", m_id + " key set to " + sc + " (" + HWP::Options::KeyName(sc) + ")");
		return Done();
	}

	bool Back() override
	{
		HWP::Log("options", m_id + " key capture cancelled");
		return true; // the window manager closes us (Cleanup ends the capture)
	}

	bool Done()
	{
		if (m_tab !is null)
			m_tab.CaptureEnded();
		@m_tab = null;
		return true;
	}

	void Cleanup() override
	{
		// closed from outside (the menu force-closed): the tab stops showing it
		if (m_tab !is null)
			m_tab.CaptureEnded();
		@m_tab = null;
		AWindowObject::Cleanup();
	}
}

// one line of the list (a clone of a template in options.gui)
class HWPOptionsRow
{
	Widget@ w;
	string kind;               // section, package, mod, setting
	HWP::Config::Package@ pkg;
	HWP::Config::Mod@ mod;
	HWP::Config::Setting@ setting;
	HWPOptionsRow@ modRow;     // context the search also looks at
	HWPOptionsRow@ pkgRow;
	bool top;                  // in the top section (no package)
	TextWidget@ title;
	TextWidget@ value;
	AInteractableWidget@ button;
	string titleL;             // lower case, for the search
	string aboutL;
	string valueL;
}

class HWPOptionsTab : MenuTab
{
	array<HWPOptionsRow@> m_rows;
	ScrollbarWidget@ m_list;
	Widget@ m_tplSection;
	Widget@ m_tplPackage;
	Widget@ m_tplRow;
	TextWidget@ m_hint;
	TextInputWidget@ m_search;
	TextWidget@ m_searchHint;
	array<string> m_query;     // the search words, lower case
	string m_queryText;
	string m_capture;          // id of the KeyOption waiting for a key (HWPKeyCaptureWindow), or ""
	int m_shown;               // rows the search left

	HWPOptionsTab(GUIBuilder@ b, uint id)
	{
		super(b, id, "gui/hwp/options.gui");
		@m_hint = cast<TextWidget>(m_widget.GetWidgetById("hint"));
		@m_search = cast<TextInputWidget>(m_widget.GetWidgetById("search"));
		@m_searchHint = cast<TextWidget>(m_widget.GetWidgetById("search-hint"));
		@m_list = cast<ScrollbarWidget>(m_widget.GetWidgetById("rows"));
		@m_tplSection = m_widget.GetWidgetById("tpl-section");
		@m_tplPackage = m_widget.GetWidgetById("tpl-package");
		@m_tplRow = m_widget.GetWidgetById("tpl-row");
		// the console key's char: it opens the console, it is never part of a search
		if (m_search !is null)
		{
			m_search.m_forbiddenCharacters.insertLast("`");
			m_search.m_forbiddenCharacters.insertLast("~");
		}
	}

	void Initialize() override
	{
		Build();
		Refresh();
		RefreshInteractableWidgets(m_widget);
	}

	// ---- building -----------------------------------------------------------

	bool HasRow(const string &in id)
	{
		for (uint i = 0; i < m_rows.length(); i++)
		{
			if (m_rows[i].w.m_id == id)
				return true;
		}
		return false;
	}

	HWPOptionsRow@ AddRow(Widget@ tpl, const string &in kind, const string &in id, const string &in func)
	{
		HWPOptionsRow@ r = HWPOptionsRow();
		r.kind = kind;
		@r.w = tpl.Clone();
		// a setting shows twice (the top section and its module): the first row has the id
		r.w.SetID(HasRow(id) ? id + "-2" : id);
		r.w.m_visible = true;
		@r.title = cast<TextWidget>(r.w.GetWidgetById("title"));
		@r.value = cast<TextWidget>(r.w.GetWidgetById("value"));
		@r.button = cast<AInteractableWidget>(r.w.GetWidgetById("button"));
		if (r.button !is null)
		{
			r.button.m_func = func;
			r.button.m_navPos = ivec2(0, m_rows.length());
		}
		m_list.AddChild(r.w);
		m_rows.insertLast(r);
		return r;
	}

	HWPOptionsRow@ AddSetting(HWP::Config::Setting@ s, HWPOptionsRow@ modRow, HWPOptionsRow@ pkgRow)
	{
		HWPOptionsRow@ r;
		if (s.IsOption())
			@r = AddRow(m_tplRow, "setting", "hwp-opt-" + s.option, "hwp-opt " + s.option);
		else
			@r = AddRow(m_tplRow, "setting", "hwp-cfg-" + s.key, "hwp-cfg " + s.key);
		@r.setting = s;
		r.top = modRow is null;
		@r.modRow = modRow;
		@r.pkgRow = pkgRow;
		if (modRow !is null)
		{
			@r.mod = modRow.mod;
			@r.pkg = modRow.pkg;
		}
		if (r.title !is null)
			r.title.m_offset.x = r.top ? 4 : 14;
		r.aboutL = s.About().toLower();
		return r;
	}

	void Build()
	{
		m_list.ClearChildren();
		m_rows.removeRange(0, m_rows.length());
		if (!HWP::Config::g_loaded)
			HWP::Config::Init();

		// the top section: packages.json settings_top, then any option the config does not list
		array<HWP::Config::Setting@> top = HWP::Config::g_top;
		auto ids = HWP::Options::g_options.getKeys();
		ids.sortAsc();
		for (uint i = 0; i < ids.length(); i++)
		{
			if (HWP::Config::Find("", ids[i]) is null)
			{
				HWP::Config::Setting@ s = HWP::Config::Setting();
				s.option = ids[i];
				top.insertLast(s);
			}
		}
		if (top.length() > 0)
		{
			auto sec = AddRow(m_tplSection, "section", "hwp-top", "");
			sec.top = true;
			SetText(sec.title, Resources::GetString(".hwp.options.top"));
			for (uint i = 0; i < top.length(); i++)
				AddSetting(top[i], null, null);
		}

		for (uint p = 0; p < HWP::Config::g_packages.length(); p++)
		{
			auto pkg = HWP::Config::g_packages[p];
			auto pr = AddRow(m_tplPackage, "package", "hwp-pkg-" + pkg.id, "hwp-pkg " + pkg.id);
			@pr.pkg = pkg;
			pr.titleL = pkg.Title().toLower();
			for (uint m = 0; m < pkg.mods.length(); m++)
			{
				auto mod = pkg.mods[m];
				auto mr = AddRow(m_tplRow, "mod", "hwp-mod-" + mod.id, "hwp-mod " + mod.id);
				@mr.pkg = pkg;
				@mr.mod = mod;
				@mr.pkgRow = pr;
				if (mr.title !is null)
					mr.title.m_offset.x = 6;
				mr.titleL = mod.Title().toLower();
				mr.aboutL = mod.About().toLower();
				for (uint i = 0; i < mod.settings.length(); i++)
					AddSetting(mod.settings[i], mr, pr);
			}
		}
		HWP::Log("options", "built " + m_rows.length() + " rows, " + HWP::Config::g_packages.length() + " package(s)");
	}

	// ---- every frame ----------------------------------------------------------

	void SetText(TextWidget@ t, const string &in text)
	{
		if (t !is null && t.m_str != text)
			t.SetText(text);
	}

	void SetColor(TextWidget@ t, const vec4 &in c)
	{
		if (t is null || (t.m_color.x == c.x && t.m_color.y == c.y && t.m_color.z == c.z && t.m_color.w == c.w))
			return;
		t.SetColor(c);
		t.SetText(t.m_str, true, true);
	}

	bool Open(HWP::Config::Package@ pkg)
	{
		return pkg !is null && HWP::Options::g_open.find(pkg.id) >= 0;
	}

	// a row's texts and button, for the current value
	void Fill(HWPOptionsRow@ r)
	{
		vec4 white = vec4(1, 1, 1, 1);
		vec4 dim = vec4(0.5f, 0.5f, 0.5f, 1);
		vec4 soft = vec4(0.82f, 0.82f, 0.82f, 1);
		if (r.kind == "package")
		{
			int on = 0;
			for (uint i = 0; i < r.pkg.mods.length(); i++)
				on += r.pkg.mods[i].On() ? 1 : 0;
			SetText(r.title, (Open(r.pkg) || m_query.length() > 0 ? "- " : "+ ") + r.pkg.Title());
			SetText(r.value, Resources::GetString(".hwp.options.count", { { "on", on }, { "n", r.pkg.mods.length() } }));
		}
		else if (r.kind == "mod")
		{
			bool on = r.mod.On();
			SetText(r.title, r.mod.Title());
			SetColor(r.title, on ? white : dim);
			string v = r.mod.CanToggle() ? HWP::Config::OnOff(on) : Resources::GetString(".hwp.cfg.always");
			SetText(r.value, v);
			r.valueL = v.toLower();
			r.button.m_enabled = r.mod.CanToggle() && !r.mod.Locked();
			SetColor(r.value, r.button.m_enabled ? white : dim);
		}
		else if (r.kind == "setting")
		{
			auto s = r.setting;
			string title = s.Title();
			SetText(r.title, title);
			r.titleL = title.toLower();
			bool live = r.mod is null || r.mod.On();
			SetColor(r.title, !live ? dim : (r.top ? white : soft));
			string v = s.IsOption() && s.option == m_capture ? Resources::GetString(".hwp.options.press") : s.Value();
			SetText(r.value, v);
			r.valueL = v.toLower();
			r.button.m_enabled = !s.Locked();
			SetColor(r.value, r.button.m_enabled ? white : dim);
		}
	}

	// fuzzy: the letters in order; a substring scores most, then runs and word starts
	int Fuzzy(const string &in text, const string &in q)
	{
		int at = text.findFirst(q);
		if (at >= 0)
			return 1000 - at + ((at == 0 || text[at - 1] == 32) ? 500 : 0);
		int score = 0;
		uint ti = 0;
		int run = 0;
		int gaps = 0;
		for (uint qi = 0; qi < q.length(); qi++)
		{
			uint8 c = q[qi];
			bool found = false;
			while (ti < text.length())
			{
				uint8 t = text[ti];
				bool start = ti == 0 || text[ti - 1] == 32;
				ti++;
				if (t == c)
				{
					score += 10 + (run > 0 ? 15 : 0) + (start ? 20 : 0);
					run++;
					found = true;
					break;
				}
				run = 0;
				gaps++;
			}
			if (!found)
				return 0;
		}
		return max(score - gaps, 0);
	}

	bool WordIn(HWPOptionsRow@ r, const string &in word)
	{
		if (r is null)
			return false;
		return Fuzzy(r.titleL, word) > 0 || r.valueL.findFirst(word) >= 0
			|| (word.length() >= 3 && r.aboutL.findFirst(word) >= 0);
	}

	// every word is in the row, its module or its package
	bool Matches(HWPOptionsRow@ r)
	{
		for (uint i = 0; i < m_query.length(); i++)
		{
			if (!WordIn(r, m_query[i]) && !WordIn(r.modRow, m_query[i]) && !WordIn(r.pkgRow, m_query[i]))
				return false;
		}
		return true;
	}

	bool Available(HWPOptionsRow@ r)
	{
		return r.setting is null || r.setting.Available();
	}

	// which rows show: the open packages, or what the search finds (with its headers)
	bool Layout()
	{
		bool searching = m_query.length() > 0;
		m_shown = 0;
		array<bool> show(m_rows.length());
		for (uint i = 0; i < m_rows.length(); i++)
		{
			auto r = m_rows[i];
			if (r.kind == "section")
				continue;
			if (!searching)
				show[i] = Available(r) && (r.top || r.kind == "package" || Open(r.pkg));
			else
				show[i] = Available(r) && r.kind != "package" && (Matches(r)
					|| (r.setting !is null && !m_capture.isEmpty() && r.setting.option == m_capture));
			if (show[i] && r.kind != "package")
				m_shown++;
		}
		// a row's module and package show over it
		for (uint i = 0; i < m_rows.length(); i++)
		{
			if (!show[i])
				continue;
			auto r = m_rows[i];
			for (uint j = 0; j < i; j++)
			{
				if (m_rows[j] is r.modRow || m_rows[j] is r.pkgRow)
					show[j] = true;
			}
		}
		// the top section's label shows over any of its rows
		for (uint i = 0; i < m_rows.length(); i++)
		{
			if (m_rows[i].kind != "section")
				continue;
			for (uint j = i + 1; j < m_rows.length() && m_rows[j].top; j++)
				show[i] = show[i] || show[j];
		}
		bool changed = false;
		for (uint i = 0; i < m_rows.length(); i++)
		{
			if (m_rows[i].w.m_visible == show[i])
				continue;
			m_rows[i].w.m_visible = show[i];
			changed = true;
		}
		return changed;
	}

	// the row under the mouse, or the keyboard/gamepad selection in the list
	HWPOptionsRow@ Selected()
	{
		if (m_list is null || !m_list.m_hovering)
			return null;
		AInteractableWidget@ b = m_list.m_input.m_hovering;
		if (b is null && !m_list.m_input.m_usingMouse)
			@b = m_list.m_input.GetCurrentInteractable();
		if (b is null)
			return null;
		for (uint i = 0; i < m_rows.length(); i++)
		{
			if (m_rows[i].button is b)
				return m_rows[i];
		}
		return null;
	}

	string Hint()
	{
		auto opt = HWP::Options::Get(m_capture);
		if (opt !is null)
			return Resources::GetString(".hwp.options.capture", { { "what", opt.Title() } });
		if (m_query.length() > 0 && m_shown == 0)
			return Resources::GetString(".hwp.options.nomatch", { { "q", m_queryText } });
		auto r = Selected();
		if (r is null)
			return Resources::GetString(".hwp.options.hint");
		string about;
		bool level = false;
		bool locked = false;
		if (r.kind == "package")
			about = Resources::GetString(Open(r.pkg) ? ".hwp.options.close" : ".hwp.options.open");
		else if (r.kind == "mod")
		{
			about = r.mod.About();
			if (!r.mod.CanToggle())
				about += " " + r.mod.AlwaysOn();
			level = r.mod.level && r.mod.CanToggle();
			locked = r.mod.Locked() && r.mod.CanToggle();
		}
		else if (r.setting !is null)
		{
			about = r.setting.About();
			if (about.isEmpty())
				about = Resources::GetString(".hwp.options.hint");
			level = r.setting.level && !r.setting.IsOption();
			locked = r.setting.Locked();
		}
		if (locked)
			about += " " + Resources::GetString(".hwp.options.host");
		else if (level)
			about += " " + Resources::GetString(".hwp.options.level");
		return about;
	}

	void Refresh()
	{
		for (uint i = 0; i < m_rows.length(); i++)
		{
			if (m_rows[i].kind != "section")
				Fill(m_rows[i]);
		}
		if (Layout() && m_list !is null)
		{
			m_list.Invalidate();
			// the list keeps its own navigation (ScrollbarWidget::m_input, outside the
			// window's): with the selection in it, its next layout rebuilds it in place
			if (!m_list.m_hovering)
				m_list.m_input.RefreshInteractableWidgets(m_list);
			Invalidate();
		}
		SetText(m_hint, Hint());
		if (m_searchHint !is null)
		{
			bool empty = m_search is null || (m_search.m_text.length() == 0 && !m_search.m_typing);
			if (m_searchHint.m_visible != empty)
				m_searchHint.m_visible = empty;
		}
	}

	void SetQuery(const string &in text)
	{
		string q = text.toLower();
		// (trimmed: a trailing space should not hide everything)
		while (q.length() > 0 && q.substr(q.length() - 1) == " ")
			q = q.substr(0, q.length() - 1);
		while (q.length() > 0 && q.substr(0, 1) == " ")
			q = q.substr(1);
		if (q == m_queryText)
			return;
		m_queryText = q;
		m_query.removeRange(0, m_query.length());
		auto words = q.split(" ");
		for (uint i = 0; i < words.length(); i++)
		{
			if (!words[i].isEmpty())
				m_query.insertLast(words[i]);
		}
		if (m_list !is null)
			m_list.m_handleValue = 0;
		Refresh();
	}

	void CaptureEnded()
	{
		m_capture = "";
		Refresh();
	}

	void StartCapture(const string &in id)
	{
		if (m_manager is null)
			return;
		m_capture = id;
		m_manager.AddWindowObject(HWPKeyCaptureWindow(m_builder, this, id));
	}

	bool Update(int ms, GameInput& gameInput, MenuInput& menuInput) override
	{
		Refresh();
		return AWindowObject::Update(ms, gameInput, menuInput);
	}

	void OnFunc(Widget@ sender, const string &in name) override
	{
		if (name == "hwp-search" && m_search !is null)
		{
			SetQuery(m_search.m_text.plain());
			return;
		}
		if (name == "hwp-search-clear" && m_search !is null)
		{
			m_search.SetText("");
			SetQuery("");
			return;
		}
		auto parse = name.split(" ");
		if (parse.length() < 2)
			return;
		string id = parse[1];
		// hwp-pkg opens/closes a package; hwp-open/hwp-close (GameLab) set it
		if (parse[0] == "hwp-pkg" || parse[0] == "hwp-open" || parse[0] == "hwp-close")
		{
			auto pkg = HWP::Config::GetPackage(id);
			if (pkg is null)
				return;
			bool open = parse[0] == "hwp-pkg" ? !Open(pkg) : parse[0] == "hwp-open";
			int at = HWP::Options::g_open.find(id);
			if (open && at < 0)
				HWP::Options::g_open.insertLast(id);
			else if (!open && at >= 0)
				HWP::Options::g_open.removeAt(at);
			HWP::Log("options", "package " + id + (open ? " opened" : " closed"));
		}
		else if (parse[0] == "hwp-mod")
		{
			auto mod = HWP::Config::GetMod(id);
			if (mod is null)
				return;
			mod.Toggle();
			HWP::Log("options", id + " -> " + (mod.On() ? "on" : "off"));
		}
		else if (parse[0] == "hwp-cfg")
		{
			auto s = HWP::Config::Find(id, "");
			if (s is null)
				return;
			s.Next();
			HWP::Log("options", id + " -> " + s.Value());
		}
		else if (parse[0] == "hwp-opt")
		{
			auto opt = HWP::Options::Get(id);
			if (opt is null)
				return;
			if (cast<HWP::Options::KeyOption>(opt) !is null)
			{
				if (m_capture.isEmpty())
					StartCapture(id);
			}
			else
			{
				opt.Next();
				HWP::Log("options", id + " -> " + opt.Value());
			}
		}
		Refresh();
	}
}

// In playermenu.gui: on its first update, finds the PlayerMenu it belongs to
// and adds the HammerwatchPlus tab (last, matching the last tab button).
class HWPOptionsHookWidget : GroupWidget
{
	bool m_done;

	HWPOptionsHookWidget()
	{
		super();
	}

	Widget@ Clone() override
	{
		HWPOptionsHookWidget@ w = HWPOptionsHookWidget();
		CloneInto(w);
		return w;
	}

	void Update(int dt) override
	{
		GroupWidget::Update(dt);
		if (m_done)
			return;
		auto gm = cast<BaseGameMode>(g_gameMode);
		if (gm is null || gm.m_windowManager is null)
			return;
		Widget@ root = this;
		while (root.m_parent !is null)
			@root = root.m_parent;
		for (uint i = 0; i < gm.m_windowManager.m_objects.length(); i++)
		{
			auto menu = cast<PlayerMenu>(gm.m_windowManager.m_objects[i]);
			if (menu is null || menu.m_widget !is root)
				continue;
			m_done = true;
			uint id = HashString("hwp_options");
			for (uint j = 0; j < menu.m_tabSystem.m_tabs.length(); j++)
			{
				if (menu.m_tabSystem.m_tabs[j].m_id == id)
					return;
			}
			menu.m_tabSystem.AddTab(HWPOptionsTab(menu.m_builder, id));
			return;
		}
	}
}

ref@ LoadHWPOptionsHookWidget(WidgetLoadingContext &ctx)
{
	HWPOptionsHookWidget@ w = HWPOptionsHookWidget();
	w.Load(ctx);
	return w;
}

namespace HWPOptions
{
	[Hook]
	void LoadWidgetProducers(GUIBuilder@ builder)
	{
		builder.AddWidgetProducer("hwp-options-hook", LoadHWPOptionsHookWidget);
	}
}
