// GameLab UI probes: where a widget is on screen, and what the top window's mouse
// hit-test can reach, so a scenario can click it with a posted mouse message (the
// runner's `click` / `hover` steps) or press it through its own handlers (gamelab-hands
// `press`).
//
// Coordinates. A window lays its widgets out from (0,0) (IWidgetHoster::DoLayout) and is
// drawn translated by its m_origin, so a widget sits at host.m_origin + widget.m_origin in
// GUI units; WindowInput::UpdateMouseInputs hit-tests exactly that rectangle. A HUD
// component is drawn at (origin + m_offset) * m_scale (HUDComponent::Draw). GUI units
// times g_gameMode.m_wndScale are window pixels: BaseGameMode::ResizeWindow divides the
// window size by it, and MouseBase/WindowManager divide GameInput.MousePos (pixels) by it.
namespace GameLab
{
	const uint CLICK_CAP = 120;

	// x/y: top-left in GUI units; px/py: the centre in window client pixels
	void WidgetPos(Json@ n, Widget@ w, vec2 origin, float hostScale)
	{
		float s = g_gameMode.m_wndScale * hostScale;
		n.Num("x", (origin.x + w.m_origin.x) * hostScale).Num("y", (origin.y + w.m_origin.y) * hostScale)
			.Int("px", int((origin.x + w.m_origin.x + w.m_width / 2.0f) * s))
			.Int("py", int((origin.y + w.m_origin.y + w.m_height / 2.0f) * s));
	}

	// the GUI space and where the game thinks the mouse is: GetMousePos (pixels, what the
	// windows hit-test after dividing by scale) and whether it came from a real pointer
	// (MouseBase.m_real: GameInput.MousePos was >= 0)
	string ScreenJson()
	{
		Json s;
		s.Num("scale", g_gameMode.m_wndScale).Int("w", g_gameMode.m_wndWidth).Int("h", g_gameMode.m_wndHeight)
			.Int("pw", int(g_gameMode.m_wndWidth * g_gameMode.m_wndScale))
			.Int("ph", int(g_gameMode.m_wndHeight * g_gameMode.m_wndScale));
		auto gm = cast<BaseGameMode>(g_gameMode);
		if (gm !is null)
		{
			vec2 m = gm.GetMousePos();
			s.Num("mouseX", m.x).Num("mouseY", m.y);
			if (gm.m_mice.length() > 0)
				s.Bool("mouseReal", gm.m_mice[0].m_real);
			if (gm.m_currInput !is null)
				s.Num("inputMouseX", gm.m_currInput.MousePos.x).Num("inputMouseY", gm.m_currInput.MousePos.y);
		}
		return s.Close();
	}

	// own flag and every ancestor's: WindowInput only checks the widget's own m_visible,
	// so a widget inside a hidden group still hit-tests (shown=false, visible=true)
	bool Shown(Widget@ w)
	{
		for (Widget@ p = w; p !is null; @p = p.m_parent)
		{
			if (!p.m_visible)
				return false;
		}
		return true;
	}

	AWindowObject@ TopWindowObject()
	{
		auto gm = cast<BaseGameMode>(g_gameMode);
		if (gm is null || gm.m_windowManager is null || gm.m_windowManager.m_objects.length() == 0)
			return null;
		return cast<AWindowObject>(gm.m_windowManager.m_objects[gm.m_windowManager.m_objects.length() - 1]);
	}

	// the window's interactables in its hit-test order: mouse-only ones first, then the
	// navigation grid (WindowInput::UpdateMouseInputs)
	array<AInteractableWidget@>@ Interactables(AWindowObject@ win)
	{
		array<AInteractableWidget@> res;
		if (win is null || win.m_input is null)
			return res;
		for (uint i = 0; i < win.m_input.m_onlyMouseInteractables.length(); i++)
			res.insertLast(win.m_input.m_onlyMouseInteractables[i]);
		for (uint x = 0; x < win.m_input.m_interactables.length(); x++)
		{
			for (uint y = 0; y < win.m_input.m_interactables[x].length(); y++)
				res.insertLast(win.m_input.m_interactables[x][y]);
		}
		return res;
	}

	string ClickableJson(AWindowObject@ win, AInteractableWidget@ w)
	{
		Json n;
		n.Str("window", Reflect::GetTypeName(win)).Str("id", w.m_id).Str("type", Reflect::GetTypeName(w))
			.Str("func", w.m_func).Bool("enabled", w.Enabled()).Bool("visible", w.Visible()).Bool("shown", Shown(w))
			.Bool("hovering", w.m_hovering).Int("w", w.m_width).Int("h", w.m_height);
		WidgetPos(n, w, win.m_origin, 1.0f);
		auto b = cast<ButtonWidget>(w);
		if (b !is null)
			n.Str("text", b.m_text);
		return n.Close();
	}

	// clickables [top|all] [widgetId]: read-only. What a mouse click can reach: the
	// interactable widgets the window's own hit-test walks (WindowInput::UpdateMouseInputs),
	// in its order, for the top window (the only one WindowManager::Update gives input) or
	// every window ("all"), optionally only those with one id. Per widget: window, id,
	// type, func, enabled, visible (the flag the hit-test checks), shown (every ancestor
	// visible too), hovering, text (ButtonWidget), x/y/w/h in GUI units and px/py, its centre
	// in window pixels (what a `click` step posts). Capped at CLICK_CAP, truncation reported.
	void VerbClickables(const string &in id, array<string>@ args)
	{
		bool all = false;
		string want = "";
		for (uint i = 0; i < args.length(); i++)
		{
			if (i == 0 && (args[i] == "all" || args[i] == "top"))
				all = args[i] == "all";
			else
				want = args[i];
		}
		auto gm = cast<BaseGameMode>(g_gameMode);
		array<AWindowObject@> wins;
		if (gm !is null && gm.m_windowManager !is null)
		{
			uint n = gm.m_windowManager.m_objects.length();
			for (uint i = (all || n == 0) ? 0 : n - 1; i < n; i++)
			{
				auto win = cast<AWindowObject>(gm.m_windowManager.m_objects[i]);
				if (win !is null)
					wins.insertLast(win);
			}
		}
		array<string> items;
		int cut = 0;
		for (uint k = 0; k < wins.length(); k++)
		{
			auto list = Interactables(wins[k]);
			for (uint i = 0; i < list.length(); i++)
			{
				if (want != "" && list[i].m_id != want)
					continue;
				if (items.length() >= CLICK_CAP)
				{
					cut++;
					continue;
				}
				items.insertLast(ClickableJson(wins[k], list[i]));
			}
		}
		Emit(Reply(id, true).Str("top", TopWindow()).Raw("screen", ScreenJson()).Int("count", items.length())
			.Int("truncated", cut).Raw("items", RawArray(items)));
	}

	// one widget as a scenario asserts on it: what it shows and whether it can be clicked
	string WidgetJson(Widget@ w, const string &in root, vec2 origin, float hostScale)
	{
		Json n;
		n.Str("root", root).Str("id", w.m_id).Str("type", Reflect::GetTypeName(w)).Bool("visible", w.m_visible)
			.Bool("shown", Shown(w)).Int("w", w.m_width).Int("h", w.m_height);
		WidgetPos(n, w, origin, hostScale);
		auto t = cast<TextWidget>(w);
		if (t !is null)
			n.Str("text", t.m_str);
		auto b = cast<ButtonWidget>(w);
		if (b !is null)
			n.Str("text", b.m_text);
		auto ia = cast<AInteractableWidget>(w);
		if (ia !is null)
			n.Str("func", ia.m_func).Bool("enabled", ia.Enabled()).Bool("hovering", ia.m_hovering);
		auto cb = cast<CheckBoxWidget>(w);
		if (cb !is null)
			n.Bool("checked", cb.IsChecked());
		int kids = w.m_children is null ? 0 : int(w.m_children.length());
		n.Int("children", kids);
		return n.Close();
	}

	// cinema: read-only. The cinematic state (Modules/CinemaManager.as): while ms > 0 with
	// frozen set, Player.as:1388-1395 walks the player to forceMoveTarget and ignores its
	// input (a town arrival does this), so a teleport or an input is undone until it ends.
	void VerbCinema(const string &in id, array<string>@ args)
	{
		auto j = Reply(id, true).Bool("active", CinemaManager::g_cinematicC > 0).Int("ms", CinemaManager::g_cinematicC)
			.Bool("frozen", CinemaManager::g_frozenControls).Bool("camera", CinemaManager::g_overtakenCamera);
		if (CinemaManager::g_forceMoveTarget.IsValid())
		{
			vec3 t = CinemaManager::g_forceMoveTarget.GetPosition();
			j.Num("moveX", t.x).Num("moveY", t.y).Num("moveSpeed", CinemaManager::g_forceMoveSpeed);
		}
		Emit(j);
	}

	// widget <widgetId> [n] [top|all]: read-only. One widget by id, depth-first through the top
	// window (default) or every window and the HUD ("all"): root, type, visible, shown (every
	// ancestor visible too), size, x/y (GUI units) and px/py (centre, window pixels), text
	// (TextWidget / ButtonWidget), func/enabled/hovering (interactables), checked (CheckBox),
	// child count. count = how many widgets share the id; n picks one (default 0). Not found is
	// ok:true with count 0, so a scenario can assert a widget is absent.
	void VerbWidget(const string &in id, array<string>@ args)
	{
		if (args.length() < 1)
		{
			Fail(id, "usage: widget <widgetId> [n] [top|all]");
			return;
		}
		uint want = 0;
		bool all = false;
		for (uint i = 1; i < args.length(); i++)
		{
			if (args[i] == "all" || args[i] == "top")
				all = args[i] == "all";
			else
				want = uint(parseInt(args[i]));
		}
		array<string> found;
		auto gm = cast<BaseGameMode>(g_gameMode);
		if (gm !is null && gm.m_windowManager !is null)
		{
			uint n = gm.m_windowManager.m_objects.length();
			for (uint i = (all || n == 0) ? 0 : n - 1; i < n; i++)
			{
				auto win = cast<IWidgetHoster>(gm.m_windowManager.m_objects[i]);
				if (win is null || win.m_widget is null)
					continue;
				auto ws = win.m_widget.GetWidgetsById(args[0]);
				for (uint k = 0; k < ws.length(); k++)
					found.insertLast(WidgetJson(ws[k], Reflect::GetTypeName(gm.m_windowManager.m_objects[i]), win.m_origin, 1.0f));
			}
		}
		auto hud = GetHUD();
		if (all && hud !is null)
		{
			if (hud.m_widget !is null)
			{
				auto ws = hud.m_widget.GetWidgetsById(args[0]);
				for (uint k = 0; k < ws.length(); k++)
					found.insertLast(WidgetJson(ws[k], "HUD", hud.m_origin, 1.0f));
			}
			for (uint c = 0; c < hud.m_components.length(); c++)
			{
				auto comp = hud.m_components[c];
				if (comp.m_widget is null)
					continue;
				auto ws = comp.m_widget.GetWidgetsById(args[0]);
				for (uint k = 0; k < ws.length(); k++)
					found.insertLast(WidgetJson(ws[k], "HUD:" + Reflect::GetTypeName(comp), comp.m_offset, comp.m_scale));
			}
		}
		auto j = Reply(id, true).Str("top", TopWindow()).Int("count", found.length());
		if (want < found.length())
			j.Raw("widget", found[want]);
		Emit(j);
	}
}

namespace Modules
{
	class GameLabUiProbeModule : Module
	{
		GameLabUiProbeModule()
		{
			super("gamelab-probe-ui");
			GameLab::RegisterVerb("clickables", "[top|all] [widgetId]", GameLab::Verb(GameLab::VerbClickables));
			GameLab::RegisterVerb("widget", "<widgetId> [n] [top|all]", GameLab::Verb(GameLab::VerbWidget));
			GameLab::RegisterVerb("cinema", "", GameLab::Verb(GameLab::VerbCinema));
		}
	}
}
