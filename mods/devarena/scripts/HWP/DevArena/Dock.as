// The dock (docs/devarena/SPEC.md, "Dock"): an immediate-mode overlay on the right of the
// screen, drawn from the module's RenderWidgets the way the engine's own debug overlays are
// (Modules/DebugModule.as), not a WindowManager window, so the game keeps running behind it.
// F1 toggles it (the default; every dev arena hotkey is rebindable in the Plus tab).
//
// Immediate mode. One function per tab lays the dock out through a Ui. UpdateFrame runs it with
// no SpriteBatch: it records every clickable rect (da-dock lists them for scenarios) and takes
// this frame's click. RenderWidgets runs the same function again and draws. Nothing about the
// layout is stored between frames.
//
// Mouse capture. While the pointer is over the open dock the module takes input focus at
// PLAYERMENU priority, as an open game window does (GUI/WindowManager.as:146). The player
// then reads no attack, skill, aim or movement input (Player.as:1282-1283,
// PlayerTargetingHelper.as:229), from the next frame (main.as Focus: Obtain this frame,
// Update at the start of the next). Off the dock, nothing is taken (spike-dock 20261020-223329).
//
// Resolution. Everything is laid out in the engine's UI units (m_wndWidth x m_wndHeight,
// window pixels / m_wndScale, BaseGameMode::ResizeWindow), the units the HUD uses, so the
// dock keeps its size relative to the HUD at 640x360, 1080p and 1440p and follows ui_scale.
// Row heights come from the font, not constants. The width is a share of the screen, clamped
// so it neither crushes the text on a narrow UI nor swallows a wide one. Rect edges are
// snapped to whole window pixels: the scale is fractional (0.833 at 640x360) and an edge
// between pixels blurs or leaves a seam.
//
// Clicks come in as MenuInput.Forward (mouse_left is MenuForward in the kbm menu map,
// res/controls_default.cfg:31), read in UpdateFrame after the windows ran.
namespace HWP
{
namespace DevArena
{
	// SDL scancodes: the hotkeys' defaults (rebindable, HotkeyOption below)
	const int SCANCODE_F1 = 58;
	const int SCANCODE_F2 = 59;
	const int SCANCODE_Z = 29;
	const int SCANCODE_Y = 28;
	// Ctrl stays the undo/redo modifier; only the letter is bound
	const int SCANCODE_LCTRL = 224;
	const int SCANCODE_RCTRL = 228;

	const float DOCK_FRAC = 0.35f;   // of the UI width,
	const float DOCK_MIN_W = 260;    // clamped (UI units)
	const float DOCK_MAX_FRAC = 0.5f;
	// The HUD's bottom bar draws over the dock, so where they overlap the dock stops above it.
	// Measured, not read from the HUD: centred, ~142 UI units each side, ~30 tall (res 20261021-021235,
	// 2560x1440 at scale 3; at 1920x1080 the Tune dock's edge, 624, just clears its 620).
	const float HUD_HALF_W = 146;
	const float HUD_H = 34;
	const float PAD = 4;             // UI units

	bool g_dockOpen;
	bool g_dockHover;
	int g_dockToggles;
	int g_dockClicks;
	int g_dockBlocked;               // frames the dock held input focus
	int g_dockDrawn;                 // frames the dock was drawn
	bool g_lastPaused;
	vec2 g_mouseUi;
	string g_dockLastButton;
	string g_tab = "tune";
	float g_scroll;                  // content scroll, UI units
	float g_contentH;                // content height last laid out
	int g_hotkeys;                   // A/B, undo/redo, arena keys taken

	const array<string> TABS = { "tune", "loadout", "arena", "golem", "bench", "compose" };
	const array<string> TAB_LABELS = { "Tune", "Loadout", "Arena", "Golem", "Bench", "Compose" };

	BitmapFont@ g_dockFont;

	// near-black, so the panel reads the same whatever the blend does with the colour
	const vec4 COL_PANEL = vec4(0, 0, 0, 0.8f);
	const vec4 COL_BUTTON = vec4(0.06f, 0.06f, 0.09f, 0.95f);
	const vec4 COL_HOT = vec4(0.16f, 0.16f, 0.26f, 0.95f);
	const vec4 COL_ON = vec4(0.10f, 0.20f, 0.12f, 0.95f);
	const vec4 COL_EDIT = vec4(0.22f, 0.18f, 0.04f, 0.95f);
	const vec4 COL_TEXT = vec4(1, 1, 1, 1);
	const vec4 COL_DIM = vec4(0.6f, 0.6f, 0.65f, 1);
	const vec4 COL_HEAD = vec4(1, 0.85f, 0.4f, 1);
	const vec4 COL_ERR = vec4(1, 0.4f, 0.35f, 1);
	const vec4 COL_SUB = vec4(0.5f, 0.8f, 1, 1);
	const vec4 COL_BAR = vec4(0.35f, 0.6f, 0.35f, 1);

	class Hit
	{
		string id;
		vec4 rect;
	}

	// one pass over the layout: no SpriteBatch = the update pass (hits + the click)
	class Ui
	{
		SpriteBatch@ sb;
		vec2 mouse;
		bool click;          // a press this frame, on the dock
		array<Hit@> hits;
		string clicked;      // id taken this pass
		bool targeted;       // the click is bound to `target`, the button drawn under it
		string target;

		vec4 clip;           // content area: rows outside it are neither drawn nor clickable

		bool Visible(vec4 r)
		{
			return r.y >= clip.y - 0.5f && r.y + r.w <= clip.y + clip.w + 0.5f;
		}

		float TextW(const string &in s)
		{
			return DockFont().MeasureText(s).x;
		}

		void Text(float x, float y, const string &in s, vec4 col = COL_TEXT)
		{
			if (sb !is null && Visible(vec4(x, y, 0, LineH())))
				sb.DrawString(vec2(Snap(x), Snap(y)), DockFont(), s, col);
		}

		void Fill(vec4 r, vec4 col)
		{
			if (sb !is null && Visible(r))
				sb.FillRectangle(SnapRect(r), col);
		}

		// a clickable box with a label; true on the pass that takes its click
		bool Button(const string &in id, vec4 r, const string &in label, vec4 fill = COL_BUTTON,
			vec4 col = COL_TEXT, bool clipped = true)
		{
			if (clipped && !Visible(r))
				return false;
			r = SnapRect(r);
			Hit h;
			h.id = id;
			h.rect = r;
			hits.insertLast(h);
			bool over = Inside(r, mouse);
			bool plain = fill.x == COL_BUTTON.x && fill.y == COL_BUTTON.y && fill.z == COL_BUTTON.z && fill.w == COL_BUTTON.w;
			Fill(r, over && plain ? COL_HOT : fill);
			Text(r.x + 2, r.y + 1, label, col);
			if (click && over && clicked == "" && (!targeted || id == target))
			{
				clicked = id;
				return true;
			}
			return false;
		}
	}

	BitmapFont@ DockFont()
	{
		if (g_dockFont is null)
			@g_dockFont = Resources::GetBitmapFont("gui/fonts/hw8.fnt");   // the HUD's own font
		return g_dockFont;
	}

	// a UI coordinate on a whole window pixel
	float Snap(float v)
	{
		float sc = g_gameMode.m_wndScale;
		return sc <= 0 ? v : floor(v * sc + 0.5f) / sc;
	}

	vec4 SnapRect(vec4 r)
	{
		float x0 = Snap(r.x), y0 = Snap(r.y);
		return vec4(x0, y0, Snap(r.x + r.z) - x0, Snap(r.y + r.w) - y0);
	}

	float LineH()
	{
		return DockFont().MeasureText("Ag").y;
	}

	float RowH()
	{
		return LineH() + 3;
	}

	vec4 DockRect()
	{
		float w = g_gameMode.m_wndWidth;
		float h = g_gameMode.m_wndHeight;
		float frac = g_tab == "loadout" ? LOADOUT_FRAC : DOCK_FRAC;   // the Loadout tab's two columns
		float dw = min(max(w * frac, DOCK_MIN_W), w * DOCK_MAX_FRAC);
		if (w - dw < w * 0.5f + HUD_HALF_W)
			h -= HUD_H;
		return SnapRect(vec4(w - dw, 0, dw, h));
	}

	bool Inside(vec4 r, vec2 p)
	{
		return p.x >= r.x && p.y >= r.y && p.x < r.x + r.z && p.y < r.y + r.w;
	}

	// ---- text entry -------------------------------------------------------------------
	// The way the in-game chat takes it (GUI/Menus/InGameChat.as): ExpectTextInput on the
	// control bindings, then the frame's TextInputControlEvents from GameInput; Submit (Enter)
	// and Cancel (Escape) end it. While typing, the window manager's input lock is set so
	// Escape is spent on the lock (GUI/WindowManager.as Back) instead of opening the pause
	// menu, and the dock holds input focus wherever the pointer is (spike-text 20261020-224031).
	// One field edits at a time; g_editId names it ("filter", "cell|<path>|<L>", ...).
	bool g_typing;
	string g_editId;
	utf8string g_fieldText;          // the field being edited
	utf8string g_fieldBefore;
	string g_filter;                 // the Tune tab's field filter
	int g_fieldSubmits;
	int g_fieldCancels;
	int g_fieldEvents;
	const int FIELD_LIMIT = 160;
	bool g_fieldTruncated;           // typing ran past FIELD_LIMIT

	void StartTyping(const string &in id, const string &in text)
	{
		if (g_typing)
			StopTyping(true);
		auto cb = GetControlBindings();
		if (cb !is null)
			cb.ExpectTextInput();
		cast<BaseGameMode>(g_gameMode).m_windowManager.LockInput(true);
		g_typing = true;
		g_editId = id;
		g_fieldText = text;
		g_fieldBefore = g_fieldText;
		g_fieldInFrame = false;
		g_fieldFresh = true;
		g_fieldTruncated = false;
	}

	// commit: hand the text to the field's owner (Enter, or a click elsewhere)
	void StopTyping(bool commit)
	{
		auto cb = GetControlBindings();
		if (cb !is null)
			cb.StopExpectTextInput();
		cast<BaseGameMode>(g_gameMode).m_windowManager.LockInput(false);
		g_typing = false;
		string id = g_editId;
		g_editId = "";
		if (!commit)
			return;
		g_fieldSubmits++;
		if (g_fieldTruncated)
		{
			g_lastError = "field " + id + ": longer than " + FIELD_LIMIT + " chars, not applied";
			HWP::Log("devarena", "field rejected " + id + ": longer than " + FIELD_LIMIT + " chars");
			return;
		}
		HWP::Log("devarena", "field submit " + id + " '" + g_fieldText.plain() + "'");
		if (id == "filter")
			g_filter = g_fieldText.plain();
		else if (id == "lsearch")
			g_lSearch = g_fieldText.plain();
		else if (id.findFirst("brot|") == 0)
			BenchSubmit(id, g_fieldText.plain());
		else if (id.findFirst("cmpf|") == 0)
			ComposeSubmit(id, g_fieldText.plain());
		else
			TuneSubmit(id, g_fieldText.plain());
	}

	// GameLab's command channel is text too: "!gl <id> <verb>~" frames (gamelab-probe
	// Inbox.as), read from the same events. The field skips them, so a probe sent mid-edit
	// never lands in the text; "!" and "~" are therefore not typeable here.
	bool g_fieldInFrame;
	bool g_fieldFresh;               // the text is the old value, selected: the first key replaces it

	void AddFieldText(const string &in s)
	{
		string keep;
		for (uint i = 0; i < s.length(); i++)
		{
			string ch = s.substr(i, 1);
			if (ch == "!")
				g_fieldInFrame = true;
			else if (ch == "~")
				g_fieldInFrame = false;
			else if (!g_fieldInFrame)
				keep += ch;
		}
		utf8string u = keep;
		if (keep != "" && g_fieldFresh)
		{
			g_fieldText = "";
			g_fieldFresh = false;
		}
		if (keep != "" && int(g_fieldText.length() + u.length()) <= FIELD_LIMIT)
			g_fieldText.insert(g_fieldText.length(), u);
		else if (keep != "")
			g_fieldTruncated = true;
	}

	void TickTyping(GameInput& gameInput)
	{
		int n = gameInput.GetTextInputCount();
		for (int i = 0; i < n && g_typing; i++)
		{
			auto evt = gameInput.GetTextInput(i);
			g_fieldEvents++;
			switch (evt.evt)
			{
				case TextInputControlEventType::None:
					AddFieldText(evt.text.plain());
					break;
				case TextInputControlEventType::Backspace:
					if (g_fieldFresh)
						g_fieldText = "";
					g_fieldFresh = false;
					if (g_fieldText.length() > 0)
						g_fieldText.erase(g_fieldText.length() - 1, 1);
					g_fieldTruncated = false;   // what is left is what was typed
					break;
				case TextInputControlEventType::Clear:
					g_fieldText = "";
					break;
				case TextInputControlEventType::Submit:
					StopTyping(true);
					break;
				case TextInputControlEventType::Cancel:
					g_fieldCancels++;
					g_fieldText = g_fieldBefore;   // Escape drops the edit
					StopTyping(false);
					break;
			}
		}
	}

	bool TextInputBusy()
	{
		auto cb = GetControlBindings();
		return cb !is null && cb.IsExpectingTextInput();
	}

	// a text field: shows `shown`, or the edit buffer while it is the one being edited
	bool Field(Ui@ ui, const string &in id, vec4 r, const string &in shown, vec4 col = COL_TEXT, vec4 fill = COL_BUTTON)
	{
		bool editing = g_typing && g_editId == id;
		string label = editing ? g_fieldText.plain() + "_" : shown;
		if (ui.Button(id, r, label, editing ? COL_EDIT : fill, col) && !editing)
		{
			StartTyping(id, shown);
			return true;
		}
		return false;
	}

	// ---- keys -------------------------------------------------------------------------
	array<bool> g_keyWas(256);       // by scancode

	bool KeyPressed(int scancode)
	{
		bool down = Platform::IsKeyDown(ControllerType::Keyboard, 0, scancode);
		bool was = g_keyWas[scancode];
		g_keyWas[scancode] = down;
		return down && !was;
	}

	// The hotkeys are rebindable in the player menu's Plus tab (HWP::Options ids devarena-<name>,
	// no config lists them, so they sit in its top section). The key is kept per save as
	// devarena.key.<name>, local: devarena syncs no settings prefix, so each player has their own.
	// Read live, so a bind made in the tab takes effect the same frame.
	int HotkeyScancode(const string &in name, int def)
	{
		int sc = HWP::Settings::GetInt("devarena.key." + name, def);
		return sc > 0 && sc < int(g_keyWas.length()) ? sc : def;
	}

	int KeyDock() { return HotkeyScancode("dock", SCANCODE_F1); }
	int KeyAB() { return HotkeyScancode("ab", SCANCODE_F2); }
	int KeyUndo() { return HotkeyScancode("undo", SCANCODE_Z); }
	int KeyRedo() { return HotkeyScancode("redo", SCANCODE_Y); }
	int KeyReset() { return HotkeyScancode("reset", SCANCODE_F3); }
	int KeyGolem() { return HotkeyScancode("golem", SCANCODE_F4); }
	int KeyPause() { return HotkeyScancode("pause", SCANCODE_F6); }

	// The dock draws with SpriteBatch::DrawString and measures with MeasureText, the raw text,
	// so it takes the plain name (KeyText), not the game-text one (KeyName escapes a backslash).
	string KeyLabel(int sc) { return HWP::Options::KeyText(sc); }
	// at most 4 characters, for the fixed-width buttons
	string ShortKeyLabel(int sc) { return HWP::Options::ShortKeyName(sc).replace("\\\\", "\\"); }

	class HotkeyOption : HWP::Options::KeyOption
	{
		string m_name;
		int m_default;
		bool m_ctrl;     // shown as Ctrl+<key>: Ctrl is the fixed modifier

		HotkeyOption(const string &in name, int def, bool ctrl = false)
		{
			m_name = name;
			m_default = def;
			m_ctrl = ctrl;
		}

		string Title() override { return Resources::GetString(".hwp.devarena.key." + m_name); }
		int Scancode() override { return HotkeyScancode(m_name, m_default); }
		string Value() override
		{
			string name = HWP::Options::KeyName(Scancode());
			return m_ctrl ? "Ctrl+" + name : name;
		}
		void SetScancode(int scancode) override
		{
			if (scancode == m_default)
				HWP::Settings::Reset("devarena.key." + m_name);
			else
				HWP::Settings::SetInt("devarena.key." + m_name, scancode);
			// the new key is held right now (just pressed to bind it): no hotkey
			if (scancode > 0 && scancode < int(g_keyWas.length()))
				g_keyWas[scancode] = true;
		}
	}

	// from the module ctor: options are script globals, reset every level
	void RegisterHotkeys()
	{
		HWP::Options::Register("devarena-dock", HotkeyOption("dock", SCANCODE_F1));
		HWP::Options::Register("devarena-ab", HotkeyOption("ab", SCANCODE_F2));
		HWP::Options::Register("devarena-undo", HotkeyOption("undo", SCANCODE_Z, true));
		HWP::Options::Register("devarena-redo", HotkeyOption("redo", SCANCODE_Y, true));
		HWP::Options::Register("devarena-reset", HotkeyOption("reset", SCANCODE_F3));
		HWP::Options::Register("devarena-golem", HotkeyOption("golem", SCANCODE_F4));
		HWP::Options::Register("devarena-pause", HotkeyOption("pause", SCANCODE_F6));
	}

	bool CtrlDown()
	{
		return Platform::IsKeyDown(ControllerType::Keyboard, 0, SCANCODE_LCTRL)
			|| Platform::IsKeyDown(ControllerType::Keyboard, 0, SCANCODE_RCTRL);
	}

	void TickHotkeys()
	{
		bool f1 = KeyPressed(KeyDock());
		bool f2 = KeyPressed(KeyAB());
		bool z = KeyPressed(KeyUndo());
		bool y = KeyPressed(KeyRedo());
		// the Plus tab's key capture turns text input on, so a key being bound fires nothing
		if (g_typing || TextInputBusy())
			return;
		if (f1)
		{
			g_dockOpen = !g_dockOpen;
			g_dockToggles++;
			HWP::Log("devarena", "dock " + (g_dockOpen ? "open" : "closed"));
		}
		if (f2)
		{
			g_hotkeys++;
			SwapAB();
		}
		if (CtrlDown() && (z || y))
		{
			g_hotkeys++;
			StepVersion(z ? -1 : 1);
		}
	}

	// ---- layout -----------------------------------------------------------------------
	string VersionSummary()
	{
		return "A v" + g_slotA + (g_onB ? "" : "*") + "  B " + (g_slotB < 0 ? "-" : "v" + g_slotB) + (g_onB ? "*" : "")
			+ (Pending() ? "  (pending)" : "");
	}

	void LayoutDock(Ui@ ui)
	{
		auto r = DockRect();
		float row = RowH();
		ui.Fill(r, COL_PANEL);
		float x = r.x + PAD, w = r.z - PAD * 2;
		float y = r.y + PAD;
		ui.clip = r;
		ui.Text(x, y, "Dev Arena", COL_HEAD);
		string vs = VersionSummary();
		ui.Text(x + w - ui.TextW(vs), y, vs, COL_DIM);
		y += row + 1;

		// tabs
		float tx = x;
		for (uint i = 0; i < TABS.length(); i++)
		{
			float tw = ui.TextW(TAB_LABELS[i]) + 5;
			if (ui.Button("tab-" + TABS[i], vec4(tx, y, tw, row), TAB_LABELS[i], g_tab == TABS[i] ? COL_ON : COL_BUTTON))
			{
				g_tab = TABS[i];
				g_scroll = 0;
			}
			tx += tw + 2;
		}
		y += row + PAD;

		// footer: last action, error, relaunch
		float footH = row * 2 + PAD;
		float footY = r.y + r.w - footH;
		ui.Fill(vec4(r.x, footY - 1, r.z, 1), COL_DIM);
		ui.Text(x, footY + 1, g_lastAction == "" ? "-" : g_lastAction, COL_DIM);
		if (g_lastError != "")
			ui.Text(x, footY + 1 + row, "! " + g_lastError, COL_ERR);
		else if (g_needsRelaunch)
			ui.Text(x, footY + 1 + row, "needs relaunch", COL_HEAD);
		if (g_needsRelaunch)
		{
			float bw = ui.TextW("Relaunch") + 6;
			if (ui.Button("relaunch", vec4(x + w - bw, footY + 1 + row, bw, row), "Relaunch", COL_BUTTON))
				Relaunch();
		}

		// content, scrolled
		ui.clip = vec4(r.x, y, r.z, footY - PAD - y);
		float top = y - g_scroll;
		float end = top;
		if (g_tab == "tune")
			end = LayoutTune(ui, x, top, w);
		else if (g_tab == "loadout")
			end = LayoutLoadout(ui, x, top, w);
		else if (g_tab == "arena")
			end = LayoutArena(ui, x, top, w);
		else if (g_tab == "golem")
			end = LayoutGolem(ui, x, top, w);
		else if (g_tab == "bench")
			end = LayoutBench(ui, x, top, w);
		else if (g_tab == "compose")
			end = LayoutCompose(ui, x, top, w);
		else
			ui.Text(x, top, TabLater(g_tab), COL_DIM);
		g_contentH = end - top;
	}

	string TabLater(const string &in tab)
	{
		return tab + ": not built";
	}

	// ---- frame ------------------------------------------------------------------------
	array<Hit@> g_hits;              // the update pass's clickables

	void TickDock(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused)
	{
		g_lastPaused = paused;
		TickHotkeys();
		TickArenaKeys();

		if (g_typing && !g_dockOpen)
			StopTyping(true);
		if (g_typing)
			TickTyping(gameInput);

		auto gm = cast<BaseGameMode>(g_gameMode);
		g_mouseUi = gm is null ? vec2() : gm.GetMousePos() / g_gameMode.m_wndScale;
		g_dockHover = g_dockOpen && Inside(DockRect(), g_mouseUi);
		if (!g_dockOpen)
		{
			g_hits.resize(0);
			return;
		}

		if (g_dockHover && gameInput.MouseWheelDelta != 0)
			g_scroll -= float(gameInput.MouseWheelDelta) * RowH() * 3;
		float maxScroll = max(0.0f, g_contentH - DockRect().w * 0.5f);
		g_scroll = clamp(g_scroll, 0.0f, maxScroll);

		Ui ui;
		ui.mouse = g_mouseUi;
		if (g_clickGuard > 0)
		{
			g_clickGuard--;
			menuInput.Forward.Pressed = false;
		}
		ui.click = g_dockHover && menuInput.Forward.Pressed;
		// a click anywhere but the field being edited ends the edit, keeping the text; done before
		// the layout pass, so a skill chip or the A/B swap acts after the edit landed where it was
		// typed (review 2: an Entangle castpoint went onto Trap). The field's rect is last pass's.
		// Committing a filter or search reflows the rows, so the click then goes to the button
		// that was drawn under the pointer, not whatever the new layout puts there (review 3:
		// lsearch "paladin" + a click on ranger_nature/end applied paladin_divine/end).
		if (g_typing && menuInput.Forward.Pressed)
		{
			string under = "";
			for (uint i = 0; i < g_hits.length() && under == ""; i++)
				if (Inside(g_hits[i].rect, ui.mouse))
					under = g_hits[i].id;
			if (under != g_editId || !g_dockHover)
			{
				StopTyping(true);
				// put the edit on the live skill now, so a growth +/- on this click fits the
				// values just typed (review 4: area-ttl L1=5000 + grow+ built from base 7000)
				Flush();
				ui.targeted = true;
				ui.target = under;
			}
		}
		bool wasTyping = g_typing;
		string wasEdit = g_editId;
		TickDrag(menuInput, ui.mouse);
		LayoutDock(ui);
		g_hits = ui.hits;
		if (ui.clicked != "")
		{
			g_dockClicks++;
			g_dockLastButton = ui.clicked;
		}
		if (wasTyping && g_typing && g_editId == wasEdit && menuInput.Forward.Pressed && ui.clicked != wasEdit)
			StopTyping(true);

		// a bot or replay bench drives the player through GameInput, which the menu focus would
		// eat; the mouse is left on the dock after Start (Bench.as)
		bool driving = BenchRunning() && g_benchMode != 1;
		if ((g_dockHover && !driving) || g_typing)
		{
			Focus::Obtain(Focus::PLAYERMENU);
			g_dockBlocked++;
		}
	}

	void RenderDock(SpriteBatch& sb)
	{
		if (!g_dockOpen)
		{
			RenderMiniHud(sb);
			return;
		}
		Ui ui;
		@ui.sb = sb;
		ui.mouse = g_mouseUi;
		LayoutDock(ui);
		g_dockDrawn++;
	}

	// top-left while the dock is closed (SPEC "Dock": A/B slot + version, preset, cheat flags,
	// the golem pull's DPS and hits, an armed brush; the bench joins with step 5)
	void RenderMiniHud(SpriteBatch& sb)
	{
		bool versions = g_versions.length() > 1 || g_slotB >= 0;
		string flags = (g_god ? " god" : "") + (g_noCd ? " no-cd" : "") + (g_infMana ? " mana" : "")
			+ (abs(g_speed - 1.0f) > 0.01f ? " x" + g_speed : "") + (g_freeze ? " frozen" : "")
			+ (g_unkillable ? " unkillable" : "") + (g_passive ? " passive" : "");
		bool pull = g_pull || g_pulls > 0;
		if (!versions && g_preset == "" && flags == "" && !pull && g_brushUnit < 0)
			return;
		string s = "DEV";
		if (versions)
			s += " " + VersionSummary();
		if (g_preset != "")
			s += " | " + g_preset + (g_sheetEdited ? "*" : "");
		if (flags != "")
			s += " |" + flags;
		if (pull)
			s += " | " + (g_pull ? "" : "last ") + int(PullDps()) + " dps " + g_pullHits + " hits";
		if (g_brushUnit >= 0)
			s += " | brush " + ShortUnit(BRUSH_UNITS[g_brushUnit]) + " x" + ENC_SIZES[g_brushKind];
		auto font = DockFont();
		vec2 sz = font.MeasureText(s);
		float y = g_gameMode.m_wndHeight * 0.22f;     // under the HUD's portrait block
		sb.FillRectangle(SnapRect(vec4(2, y, sz.x + 6, sz.y + 3)), COL_PANEL);
		sb.DrawString(vec2(Snap(5), Snap(y + 1)), font, s, COL_TEXT);
	}
}
}
