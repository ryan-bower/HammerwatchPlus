// Controller buttons for HWP hotkeys (issue #14). The engine's GameInput has a fixed set of
// actions (Use, Dash, Skill1-3, ...), and a mod hotkey is not one of them, so a mod reads
// a button itself: by the control map's id ("gp_dl"), resolved to the engine's code
// (Platform::ResolveInputKey) and read with Platform::IsKeyDown on each controller map
// (res/controls_default.cfg: gp1-gp4 are SDL game controllers, gamepad="true"; ds41-ds44
// raw DualShock 4 joysticks, joystick="true", with their own ids). A button is named here
// by its gp id; a ds4 map reads the same button under its ds4 id (DS4 below).
//
// What vanilla's gamepad map leaves free in gameplay: D-pad left (gp_dl, only MenuLeft)
// and the stick clicks (gp_lth, gp_rth). Every other button is a gameplay action too
// (Clash names it).
//
// GameLab: no OS input reaches the lab game. gamelab-hands' input verb holds a button
// "pad_<gp id>" by writing "gp_dl,..." to GlobalCache EMU_HELD, and its "pad" verb sets
// EMU_USING "1" to stand for a controller in use (no symbol shared: either mod loads
// without the other).
namespace HWP
{
	namespace Input
	{
		const string EMU_HELD = "hwp_pad_held";
		const string EMU_USING = "hwp_pad_using";

		// the buttons a hotkey can take (not the triggers: analog axes, the attacks)
		const array<string> GP = { "gp_a", "gp_b", "gp_x", "gp_y", "gp_lb", "gp_rb", "gp_back", "gp_start",
			"gp_du", "gp_dd", "gp_dl", "gp_dr", "gp_lth", "gp_rth" };
		const array<string> DS4 = { "ds4_cross", "ds4_circle", "ds4_square", "ds4_triangle", "ds4_l1", "ds4_r1", "ds4_share", "ds4_options",
			"ds4_dpad_up", "ds4_dpad_down", "ds4_dpad_left", "ds4_dpad_right", "ds4_l3", "ds4_r3" };

		// the gameplay actions a hotkey must not share a button with (the menu ones are
		// fine: a hotkey that reads a button skips while a window is open)
		const array<string> GAMEPLAY_ACTIONS = { "Use", "Potion", "Dash", "MainHandAttack", "OffHandAttack",
			"Skill1", "Skill2", "Skill3", "Skill4", "ActionMenu", "ActionMenuBind", "MapOverlay", "GuildHall",
			"PlayerMenu", "MenuToggle", "PlayerMap", "Ping" };

		// vanilla's gamepad map (res/controls_default.cfg), each button's gameplay action:
		// the clash check's answer while no controller map is loaded (none is until a pad
		// is plugged in)
		const array<string> VANILLA = { "Use", "Dash", "Potion", "Skill3", "Skill2", "Skill1", "PlayerMenu", "MenuToggle",
			"MapOverlay", "GuildHall", "", "ActionMenu", "", "" };

		bool Known(const string &in gp) { return GP.find(gp) >= 0; }

		// the ds4 id of a gp button, or ""
		string Ds4(const string &in gp)
		{
			int i = GP.find(gp);
			return i < 0 ? "" : DS4[i];
		}

		bool Emulated(const string &in gp)
		{
			string held = GlobalCache::Get(EMU_HELD);
			if (held.isEmpty())
				return false;
			return held.split(",").find(gp) >= 0;
		}

		// the engine's code for a map id; type None when it resolves to nothing
		int Resolve(const string &in id, ControllerType &out type)
		{
			type = ControllerType::None;
			if (id.isEmpty())
				return -1;
			return Platform::ResolveInputKey(id, type);
		}

		// the button is down on any controller (or GameLab holds it)
		bool Held(const string &in gp)
		{
			if (!Known(gp))
				return false;
			if (Emulated(gp))
				return true;
			auto gi = GetInput();
			if (gi is null)
				return false;
			// the maps of the controllers plugged in (without one, only kbm: hwp pad,
			// 20261029-000159); a pad map's Index is its controller's
			auto maps = gi.GetControlMaps();
			bool anyPadMap = false;
			for (uint i = 0; maps !is null && i < maps.length(); i++)
			{
				auto map = maps[i];
				if (map is null || !(map.Gamepad || map.Joystick))
					continue;
				anyPadMap = true;
				ControllerType type;
				int key = Resolve(map.Joystick ? Ds4(gp) : gp, type);
				if (type != ControllerType::None && Platform::IsKeyDown(type, map.Index, key))
					return true;
			}
			// a pad in use but no map of it listed: the first game controller
			if (!anyPadMap && gi.UsingGamepad)
			{
				ControllerType type;
				int key = Resolve(gp, type);
				return type != ControllerType::None && Platform::IsKeyDown(type, 0, key);
			}
			return false;
		}

		// the first button held, or ""
		string AnyHeld()
		{
			for (uint i = 0; i < GP.length(); i++)
			{
				if (Held(GP[i]))
					return GP[i];
			}
			return "";
		}

		// the local player plays with a controller now (GameInput.UsingGamepad: the last
		// device used), or GameLab stands for one
		bool UsingPad()
		{
			if (GlobalCache::Get(EMU_USING) == "1")
				return true;
			auto gi = GetInput();
			return gi !is null && gi.UsingGamepad;
		}

		// the current map is a ds4 one
		bool Ds4Map()
		{
			auto gi = GetInput();
			auto map = gi is null ? null : gi.GetCurrentMap();
			return map !is null && map.Joystick;
		}

		// the button as the game prints it (a glyph: \"inp-gp-dl"), in the current map's style
		string Name(const string &in gp)
		{
			if (!Known(gp))
				return "";
			return FormatKeyName(Ds4Map() ? Ds4(gp) : gp);
		}

		// a plain name for the console and the log
		string Plain(const string &in gp)
		{
			if (!Known(gp))
				return "none";
			return gp;
		}

		// the gameplay action a controller map binds to this button, or ""
		string Clash(const string &in gp)
		{
			auto gi = GetInput();
			if (gi is null || !Known(gp))
				return "";
			auto maps = gi.GetControlMaps();
			bool anyPadMap = false;
			for (uint i = 0; maps !is null && i < maps.length(); i++)
			{
				auto map = maps[i];
				if (map is null || !(map.Gamepad || map.Joystick))
					continue;
				anyPadMap = true;
				string id = map.Joystick ? Ds4(gp) : gp;
				auto bindings = map.GetBindings();
				for (uint j = 0; j < bindings.length(); j++)
				{
					if (bindings[j].ID == id && GAMEPLAY_ACTIONS.find(bindings[j].Action) >= 0)
						return bindings[j].Action;
				}
			}
			if (!anyPadMap)
				return VANILLA[GP.find(gp)];
			return "";
		}

		// hwp pad: the controller maps and buttons as the engine sees them (also the RE probe)
		void CmdPad(array<string>@ args)
		{
			auto gi = GetInput();
			if (gi is null)
			{
				HWP::Commands::Reply("no GameInput");
				return;
			}
			auto cur = gi.GetCurrentMap();
			HWP::Commands::Reply("pad: using gamepad " + (gi.UsingGamepad ? "yes" : "no")
				+ ", current map " + (cur is null ? "none" : cur.ID + " index " + cur.Index)
				+ (GlobalCache::Get(EMU_HELD).isEmpty() ? "" : ", GameLab holds " + GlobalCache::Get(EMU_HELD)));
			auto maps = gi.GetControlMaps();
			for (uint i = 0; maps !is null && i < maps.length(); i++)
			{
				auto map = maps[i];
				if (map is null)
					continue;
				HWP::Commands::Reply("pad: map " + map.ID + " index " + map.Index + (map.Gamepad ? " gamepad" : "")
					+ (map.Joystick ? " joystick" : "") + ", " + map.GetBindings().length() + " bindings");
			}
			auto cb = GetControlBindings();
			auto all = cb is null ? null : cb.GetMaps();
			for (uint i = 0; all !is null && i < all.length(); i++)
			{
				auto map = all[i];
				if (map !is null)
					HWP::Commands::Reply("pad: binding map " + map.ID + " index " + map.Index + (map.Gamepad ? " gamepad" : "")
						+ (map.Joystick ? " joystick" : "") + (map.SteamController ? " steam" : "") + " name '" + map.GetName() + "'");
			}
			for (uint i = 0; i < GP.length(); i++)
			{
				ControllerType t;
				int k = Resolve(GP[i], t);
				ControllerType t2;
				int k2 = Resolve(DS4[i], t2);
				string clash = Clash(GP[i]);
				HWP::Commands::Reply("pad: " + GP[i] + " = " + int(t) + ":" + k + ", " + DS4[i] + " = " + int(t2) + ":" + k2
					+ (Held(GP[i]) ? " DOWN" : "") + (clash.isEmpty() ? "" : " (" + clash + ")"));
			}
		}

		void Init()
		{
			HWP::Commands::Register("pad", " the controller maps and buttons, which are down, and their gameplay actions",
				HWP::Commands::Handler(CmdPad));
		}
	}
}
