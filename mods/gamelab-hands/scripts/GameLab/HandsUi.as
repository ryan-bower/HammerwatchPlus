// gamelab-hands UI verbs: an emulated mouse (pointer); a press on a named widget is `press`
// (Stash.as). The runner's `click` / `hover` steps aim
// with the probe's clickables (gamelab-probe ProbeUi.as) and drive `pointer`.
namespace GameLab
{
	// The emulated mouse. Posted WM_MOUSEMOVE never reaches GameInput.MousePos (ui-click
	// 20261018-055552: the game's mouse stayed at 0,0), so like the emulated controller
	// (Input.as) the pointer is written into the engine's own input objects: MousePos into
	// every GameInput, the left button as MenuInput.Forward (mouse_left is MenuForward in
	// the kbm map, res/controls_default.cfg:31).
	//
	// When. A frame runs UpdateWidgets (the script widget hosts' Update), MouseBase::Update
	// (m_pos = MousePos), WindowManager::Update (hover hit-test, Forward -> ClickDown /
	// ClickUp, GUI/WindowObject.as:74-139), then the modules (BaseGameMode.as:642-656,
	// AGameplayGameMode.as:321-333; paused frames the same order). The engine clears
	// Forward.Pressed between frames, so a write from a module never reached the windows
	// (ui-click 20261018-060136: pressedKept false, no ClickDown). So the writes happen in a
	// script widget host's Update (PointerHost, in m_widgetScriptHosts), before the mice and
	// the windows of the same frame, and the module tick after them reads what they did.
	// One step per frame.
	class PointerJob
	{
		string id;
		bool click = false;
		bool middle = false;       // mclick: a move, then g_ptrMiddlePress
		vec2 pos;
		int stage = 0;
		bool wrote = false;        // this stage's input was written before the windows ran
		string top0;
		bool posKept = false;      // MousePos still ours after the frame (the engine left it)
		vec2 mouseSeen;            // the mouse's m_pos then (GetMousePos)
		string hoverSeen;          // the top window's hovered interactable then
		bool pressedBefore = false; // the top window's m_usePressed before the press
		bool downSeen = false;     // the top window took the press (m_usePressed set: ClickDown)
		bool upSeen = false;       // ... and the release (m_usePressed cleared: ClickUp)
		bool letGo = false;        // a press left over from before was let go of first
		int frames = 0;
		// when the hovered interactable is a list (ScrollbarWidget): it runs its own press and
		// release on its rows, in its Update, before the window's (ScrollbarWidget.as:258-406,
		// WindowObject.as:59), with its own m_usePressed, and only while its m_hovering is set
		ScrollbarWidget@ list;
		string listRow;            // the list's hovered row then (type#id)
		bool listRowLive0 = false; // ... still in the list (m_parent set; ClearChildren nulls it)
		bool listRowLive1 = false; // the hovered row in the press frame is still in the list
		bool listHover0 = false;   // the list's m_hovering after the move
		bool listHover1 = false;   // ... in the press frame
		bool listPressedBefore = false;
		bool listDown = false;
		bool listUp = false;
	}

	ScrollbarWidget@ HoveredList()
	{
		auto win = TopWindowObject();
		if (win is null || win.m_input is null)
			return null;
		return cast<ScrollbarWidget>(win.m_input.m_hovering);
	}

	string ListRow(ScrollbarWidget@ l)
	{
		if (l is null || l.m_input is null || l.m_input.m_hovering is null)
			return "";
		auto h = l.m_input.m_hovering;
		return Reflect::GetTypeName(h) + (h.m_id != "" ? "#" + h.m_id : "");
	}

	bool ListRowLive(ScrollbarWidget@ l)
	{
		return l !is null && l.m_input !is null && l.m_input.m_hovering !is null && l.m_input.m_hovering.m_parent !is null;
	}
	PointerJob@ g_ptr = null;

	// `pointer <px> <py> mclick`: there is no emulated middle button in the engine's input
	// objects (MenuInput has no middle), so a middle click is the pointer move plus this count,
	// with the window pixel it was made at. Mods that take middle clicks compare the count.
	int g_ptrMiddlePress = 0;
	vec2 g_ptrMiddleAt;

	// a widget host with no widget, only there to run before the windows each frame
	class PointerHost : ScriptWidgetHost
	{
		void Update(int dt) override { PointerPre(); }
		void Draw(SpriteBatch& sb, int idt) override { }
		bool ShouldSaveExistance() override { return false; }
		void Stop() override { }
	}
	PointerHost@ g_ptrHost = null;

	void EnsurePointerHost()
	{
		auto gm = cast<BaseGameMode>(g_gameMode);
		if (gm is null)
			return;
		if (g_ptrHost is null)
			@g_ptrHost = PointerHost();
		for (uint i = 0; i < gm.m_widgetScriptHosts.length(); i++)
		{
			if (gm.m_widgetScriptHosts[i] is g_ptrHost)
				return;
		}
		gm.m_widgetScriptHosts.insertLast(g_ptrHost);
	}

	void PtrAddGi(array<GameInput@>@ list, GameInput@ gi)
	{
		if (gi is null)
			return;
		for (uint i = 0; i < list.length(); i++)
		{
			if (list[i] is gi)
				return;
		}
		list.insertLast(gi);
	}

	void PtrAddMi(array<MenuInput@>@ list, MenuInput@ mi)
	{
		if (mi is null)
			return;
		for (uint i = 0; i < list.length(); i++)
		{
			if (list[i] is mi)
				return;
		}
		list.insertLast(mi);
	}

	string HoveredId()
	{
		auto win = TopWindowObject();
		if (win is null || win.m_input is null || win.m_input.m_hovering is null)
			return "";
		return win.m_input.m_hovering.m_id;
	}

	void PtrForward(array<MenuInput@>@ mis, bool down, bool pressed, bool released)
	{
		for (uint i = 0; i < mis.length(); i++)
		{
			mis[i].Forward.Down = down;
			mis[i].Forward.Pressed = pressed;
			mis[i].Forward.Released = released;
		}
	}

	bool TopUsePressed()
	{
		auto win = TopWindowObject();
		return win !is null && win.m_usePressed;
	}

	// stray presses: the top window's m_usePressed set while no pointer job ran (only a
	// MenuForward press on a hovered widget sets it, WindowObject.as:96-119), with that frame's
	// Forward and Use (D down, P pressed, R released). The next pointer reply carries them
	// (strays, strayLog) and clears the log. Seen before most clicks after the first, with only
	// gl lines in between (ui-click 20261018-094936, pets-bowl 20261018-094748, gambler-bets
	// 20261018-095213). Source open: 4 main-Enter gl lines left none in console-enter
	// 20261018-104534 (docs/RE_NOTES.md, stray presses); see PointerPost's letGo.
	AWindowObject@ g_watchWin = null;
	bool g_watchPressed = false;
	int g_sinceJob = 0;
	uint g_cmdsAtJob = 0;   // GameLab::g_commands (gl lines dispatched) at the last reply
	uint g_watchCmds = 0;
	int g_sinceCmd = 0;     // frames since a gl line was last dispatched
	array<string> g_strays;

	string Bits(bool d, bool p, bool r)
	{
		return (d ? "D" : "-") + (p ? "P" : "-") + (r ? "R" : "-");
	}

	void WatchStray()
	{
		auto win = TopWindowObject();
		bool pressed = win !is null && win.m_usePressed;
		if (g_commands != g_watchCmds)
		{
			g_watchCmds = g_commands;
			g_sinceCmd = 0;
		}
		if (g_ptr is null && pressed && (win !is g_watchWin || !g_watchPressed))
		{
			auto gm = cast<BaseGameMode>(g_gameMode);
			string fwd = "";
			string use = "";
			if (gm !is null && gm.m_currInputMenu !is null)
				fwd = Bits(gm.m_currInputMenu.Forward.Down, gm.m_currInputMenu.Forward.Pressed, gm.m_currInputMenu.Forward.Released);
			if (gm !is null && gm.m_currInput !is null)
				use = Bits(gm.m_currInput.Use.Down, gm.m_currInput.Use.Pressed, gm.m_currInput.Use.Released);
			g_strays.insertLast("{\"framesAfterJob\":" + g_sinceJob + ",\"cmdsAfterJob\":" + (g_commands - g_cmdsAtJob)
				+ ",\"framesAfterCmd\":" + g_sinceCmd + ",\"newWindow\":" + (win !is g_watchWin ? "true" : "false")
				+ ",\"window\":" + Quote(Reflect::GetTypeName(win)) + ",\"hovered\":" + Quote(HoveredId())
				+ ",\"forward\":" + Quote(fwd) + ",\"use\":" + Quote(use) + "}");
			if (g_strays.length() > 8)
				g_strays.removeAt(0);
		}
		@g_watchWin = win;
		g_watchPressed = pressed;
		g_sinceJob++;
		g_sinceCmd++;
	}

	string StrayLog()
	{
		string s = "[";
		for (uint i = 0; i < g_strays.length(); i++)
			s += (i > 0 ? "," : "") + g_strays[i];
		return s + "]";
	}

	// before the mice and the windows: this stage's input. Stages: 0 the pointer to pos and
	// the button up; click only: 1 down (Down + Pressed), 2 held, 3 up (Released), 4 idle.
	void PointerPre()
	{
		auto j = g_ptr;
		auto gm = cast<BaseGameMode>(g_gameMode);
		if (j is null || gm is null)
			return;
		array<GameInput@> gis;
		array<MenuInput@> mis;
		PtrAddGi(gis, gm.m_currInput);
		PtrAddMi(mis, gm.m_currInputMenu);
		for (uint i = 0; i < gm.m_mice.length(); i++)
		{
			PtrAddGi(gis, gm.m_mice[i].m_inputGame);
			PtrAddMi(mis, gm.m_mice[i].m_inputMenu);
		}
		// a click wiggles 1 px, so the press and the release frames are mouse moves, as a hand's
		// are: a WindowInput re-hit-tests only when the mouse moved (WindowInput.as:84-87), and a
		// perfectly still pointer kept hovering a row the menu had since rebuilt and dropped, whose
		// click then did nothing (pets-bowl 20261018-094748: HWPPetMenu.Refresh, OnFunc idx < 0)
		vec2 at = (j.click && (j.stage == 0 || j.stage == 2)) ? j.pos + vec2(1, 0) : j.pos;
		for (uint i = 0; i < gis.length(); i++)
			gis[i].MousePos = at;
		if (j.stage == 1)
			PtrForward(mis, true, true, false);
		else if (j.stage == 2)
			PtrForward(mis, true, false, false);
		else if (j.stage == 3)
			PtrForward(mis, false, false, true);
		else
			PtrForward(mis, false, false, false);
		j.wrote = true;
	}

	// after the windows (the module tick): what this stage did, then the next stage
	void PointerPost()
	{
		EnsurePointerHost();
		WatchStray();
		auto j = g_ptr;
		if (j is null)
			return;
		j.frames++;
		if (!j.wrote)
		{
			// the host did not run this frame (just inserted, or no game mode): no stage
			if (j.frames > 30)
			{
				@g_ptr = null;
				Fail(j.id, "the pointer host never ran (30 frames)");
			}
			return;
		}
		j.wrote = false;
		auto gm = cast<BaseGameMode>(g_gameMode);
		bool done = false;
		if (j.stage == 0)
		{
			vec2 at = j.click ? j.pos + vec2(1, 0) : j.pos;
			if (gm !is null && gm.m_currInput !is null)
				j.posKept = distsq(gm.m_currInput.MousePos, at) < 0.01f;
			if (gm !is null)
				j.mouseSeen = gm.GetMousePos();
			j.hoverSeen = HoveredId();
			j.pressedBefore = TopUsePressed();
			@j.list = HoveredList();
			if (j.list !is null)
			{
				j.listRow = ListRow(j.list);
				j.listRowLive0 = ListRowLive(j.list);
				j.listHover0 = j.list.m_hovering;
				j.listPressedBefore = j.list.m_usePressed;
			}
			if (j.click)
			{
				// a press the window took but never saw released: the console's Enter, which every
				// gl line ends with, is MenuForward (res/controls_default.cfg:32) and comes down
				// and up in one frame, where the window runs only its press branch
				// (WindowObject.as:96-122), on whatever the pointer rests on. The mouse button is
				// up, so let go of it, or this press is ignored and a ScalableSpriteButtonWidget's
				// ClickUp does nothing without its ClickDown (ScalableSpriteButtonWidget.as:342-345)
				auto win = TopWindowObject();
				if (win !is null && win.m_usePressed)
				{
					win.m_usePressed = false;
					j.letGo = true;
				}
				if (j.list !is null && j.list.m_usePressed)
				{
					j.list.m_usePressed = false;
					j.letGo = true;
				}
			}
			done = !j.click;
		}
		else if (j.stage == 1)
		{
			j.downSeen = TopUsePressed();
			if (j.list !is null)
			{
				j.listHover1 = j.list.m_hovering;
				j.listRowLive1 = ListRowLive(j.list);
				j.listDown = j.list.m_usePressed;
			}
		}
		else if (j.stage == 3)
		{
			j.upSeen = j.downSeen && !TopUsePressed();
			if (j.list !is null)
				j.listUp = j.listDown && !j.list.m_usePressed;
		}
		else if (j.stage == 4)
			done = true;
		j.stage++;
		if (!done)
			return;
		@g_ptr = null;
		if (j.middle)
		{
			g_ptrMiddleAt = j.pos;
			g_ptrMiddlePress++;
		}
		auto r = Reply(j.id, true).Str("kind", j.click ? "click" : j.middle ? "mclick" : "move").Num("x", j.pos.x).Num("y", j.pos.y)
			.Str("top", j.top0).Bool("posKept", j.posKept).Num("mouseX", j.mouseSeen.x).Num("mouseY", j.mouseSeen.y)
			.Str("hovered", j.hoverSeen).Int("frames", j.frames);
		if (j.click)
			r.Bool("pressedBefore", j.pressedBefore).Bool("letGo", j.letGo).Bool("downSeen", j.downSeen).Bool("upSeen", j.upSeen);
		if (j.list !is null)
		{
			r.Str("listRow", j.listRow).Bool("listRowLive0", j.listRowLive0).Bool("listHover0", j.listHover0);
			if (j.click)
				r.Bool("listRowLive1", j.listRowLive1).Bool("listHover1", j.listHover1).Bool("listPressedBefore", j.listPressedBefore)
					.Bool("listDown", j.listDown).Bool("listUp", j.listUp);
		}
		r.Int("strays", g_strays.length()).Raw("strayLog", StrayLog());
		g_strays.removeRange(0, g_strays.length());
		g_sinceJob = 0;
		g_cmdsAtJob = g_commands;
		Emit(r.Str("topAfter", TopWindow()));
	}

	// pointer <px> <py> [move|click|mclick]: the emulated mouse, the way a player's mouse reaches
	// the windows. Moves the pointer to window pixels px,py (a clickables / widget px,py), and
	// for click presses and releases the left button (MenuForward) over the next frames.
	// Replies when done (a move after 1 frame, a click after 5): top (the top window when it
	// started), posKept / mouseX / mouseY (whether the engine kept the written MousePos and
	// where the game's mouse then was), hovered (the top window's hovered interactable id
	// after the move, "" none), downSeen / upSeen (the top window took the press and the
	// release: its m_usePressed set, then cleared; pressedBefore: it was already set, left over
	// from before the click, and letGo: so the click let go of it first),
	// frames, topAfter. Over a list (ScrollbarWidget), the same for the list, which clicks its
	// rows itself: listRow (its hovered row), listRowLive0 / listRowLive1 (that row is still in
	// the list after the move / in the press frame; a dropped row's click does nothing),
	// listHover0 / listHover1 (its m_hovering then), listPressedBefore / listDown / listUp. A
	// click wiggles 1 px on its first and third frames, as a hand does. strays / strayLog: times
	// the top window's m_usePressed was set since the last reply with no pointer job running,
	// each with framesAfterJob, cmdsAfterJob (gl lines dispatched since that reply),
	// framesAfterCmd (frames since the last gl line), newWindow, window, hovered, forward and use. A click where nothing
	// is hovered does nothing, as for a player (downSeen false). mclick is a move, then a middle
	// click counted in g_ptrMiddlePress (see there); its reply is a move's.
	void VerbPointer(const string &in id, array<string>@ args)
	{
		if (args.length() < 2)
		{
			Fail(id, "usage: pointer <px> <py> [move|click|mclick]");
			return;
		}
		if (g_ptr !is null)
		{
			Fail(id, "busy: pointer " + g_ptr.id + " has not finished");
			return;
		}
		string kind = args.length() > 2 ? args[2] : "move";
		if (kind != "move" && kind != "click" && kind != "mclick")
		{
			Fail(id, "unknown pointer action '" + kind + "' (move, click, mclick)");
			return;
		}
		PointerJob j;
		j.id = id;
		j.click = kind == "click";
		j.middle = kind == "mclick";
		j.pos = vec2(parseFloat(args[0]), parseFloat(args[1]));
		j.top0 = TopWindow();
		@g_ptr = j;
	}

	// menu-continue: input. What the main menu's Continue / Singleplayer button does
	// (GUI/WindowMainMenu.as:120-123: OnFunc "continue" in MenuState::MainMenu calls the native
	// ContinueGame()). The runner's fallback when its Enter on the main menu is not taken:
	// a mouse that passed over the watch-mode window puts the menu in mouse mode, where Enter
	// presses nothing (chest-watch 20261018-172146: three Enters lost, a typed `gl ping` answered).
	// Refused outside the main menu (a player record exists).
	void VerbMenuContinue(const string &in id, array<string>@ args)
	{
		if (GetLocalPlayerRecord() !is null)
		{
			Fail(id, "not on the main menu (a player record exists)");
			return;
		}
		ContinueGame();
		Emit(Reply(id, true).Str("did", "ContinueGame"));
	}

}

namespace Modules
{
	class GameLabUiHandsModule : Module
	{
		GameLabUiHandsModule()
		{
			super("gamelab-hands-ui");
			GameLab::RegisterVerb("menu-continue", "", GameLab::Verb(GameLab::VerbMenuContinue));
			GameLab::RegisterVerb("pointer", "<px> <py> [move|click|mclick]", GameLab::Verb(GameLab::VerbPointer));
		}

		void UpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused) override
		{
			GameLab::PointerPost();
		}
	}
}
