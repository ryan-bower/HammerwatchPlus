// The game's own keyboard binds as rows of the Plus tab ("Game keys"), so every key can be
// rebound in game: the vanilla Controls window runs only in the main menu (its key capture is
// MainMenuGameMode's). A row shows the action's keyboard keys in the kbm control map, named
// by their US keycap as vanilla does (HWP::Options::KeyName), then its mouse buttons; binding one replaces the action's keyboard keys with the new key and
// keeps its mouse buttons, the way the vanilla window stages and saves a change:
// BeginStaging, RemoveStaging / AddStaging(Axis), CommitStaging, ControlBindings::Save
// (res/controls.cfg: the game's controls, every save, shared with its Options menu).
// Esc is not offered (it cancels the capture; MenuBack / MenuToggle stay on it, as vanilla
// keeps them), so a menu is always closable whatever gets rebound.
namespace HWP
{
	namespace GameKeys
	{
		const string MAP = "kbm";
		const string PREFIX = "game-"; // option ids: hwp-opt-game-<id>
		const string GROUP = "gamekeys"; // the Plus tab's group (row hwp-pkg-gamekeys; g_open)

		class GameKeyOption : HWP::Options::KeyOption
		{
			string m_id;
			string m_action;
			int m_axis; // 0: a button; 1 / 2: the low / high half of an axis (move_y 1 is up)
			array<int> m_keys;
			int m_keysVersion = -1;

			GameKeyOption(const string &in id, const string &in action, int axis)
			{
				m_id = id;
				m_action = action;
				m_axis = axis;
			}

			string Title() override { return Resources::GetString(".hwp.gamekeys." + m_id); }

			bool Mine(ControlMapBinding@ b)
			{
				return b !is null && b.Action == m_action && (m_axis == 0 || int(b.SetAxis) == m_axis);
			}

			// the keyboard scancodes bound to the action (the map's bindings, read again after a
			// bind: the tab asks every row each frame, and the hint asks every option)
			array<int>@ Keys()
			{
				if (m_keysVersion == g_version)
					return m_keys;
				m_keysVersion = g_version;
				m_keys.removeRange(0, m_keys.length());
				m_mouse.removeRange(0, m_mouse.length());
				auto map = Map();
				if (map is null)
					return m_keys;
				auto binds = map.GetBindings();
				for (uint i = 0; i < binds.length(); i++)
				{
					if (!Mine(binds[i]))
						continue;
					int sc = KeyboardScancode(binds[i]);
					if (sc > 0 && m_keys.find(sc) < 0)
						m_keys.insertLast(sc);
					else if (binds[i].BoundControlType == ControllerType::Mouse && binds[i].BoundControlType2 == ControllerType::None
						&& m_mouse.find(binds[i].ID) < 0)
						m_mouse.insertLast(binds[i].ID);
				}
				return m_keys;
			}

			// the action's mouse buttons ("mouse_left", "mouse_4"): kept by a bind, shown after the keys
			array<string> m_mouse;

			int Scancode() override
			{
				auto keys = Keys();
				return keys.length() > 0 ? keys[0] : 0;
			}

			bool Uses(int sc) override { return Keys().find(sc) >= 0; }

			// one key by its name, two or more short (the value column is 82 pixels), then the
			// mouse buttons as the game's own icons (vanilla .input.mouse_*): primary attack on
			// the left button alone reads as that button, not "Unbound"
			string Value() override
			{
				auto keys = Keys();
				if (keys.length() == 0 && m_mouse.length() == 0)
					return Resources::GetString(".input.unbound");
				string v;
				if (keys.length() == 1)
					v = HWP::Options::FitKeyName(keys[0]);
				for (uint i = 0; keys.length() > 1 && i < keys.length() && i < 3; i++)
					v += (i > 0 ? " / " : "") + HWP::Options::ShortKeyName(keys[i]);
				for (uint i = 0; i < m_mouse.length() && i < 2; i++)
					v += (v.isEmpty() ? "" : " / ") + Resources::GetString(".input." + m_mouse[i]);
				return v;
			}

			string SearchText() override
			{
				auto keys = Keys();
				string t;
				for (uint i = 0; i < keys.length(); i++)
					t += " " + HWP::Options::KeyText(keys[i]);
				return t;
			}

			void SetScancode(int sc) override
			{
				auto map = Map();
				auto cb = GetControlBindings();
				if (map is null || cb is null)
				{
					HWP::Log("gamekeys", m_id + ": no " + MAP + " control map, not bound");
					return;
				}
				map.BeginStaging();
				// collected first (as MenuControlInputWidget::Clear does): the staging array
				// may be the engine's own, which RemoveStaging shrinks under the loop
				array<ControlMapBinding@> old;
				auto staged = map.GetStaging();
				for (uint i = 0; i < staged.length(); i++)
				{
					if (Mine(staged[i]) && KeyboardScancode(staged[i]) > 0)
						old.insertLast(staged[i]);
				}
				for (uint i = 0; i < old.length(); i++)
					map.RemoveStaging(old[i]);
				int removed = int(old.length());
				if (m_axis == 0)
					map.AddStaging(ControllerType::Keyboard, sc, m_action);
				else
					map.AddStagingAxis(ControllerType::Keyboard, sc, m_action, m_axis == 1 ? ControlBindingSetAxis::Low : ControlBindingSetAxis::High);
				map.CommitStaging();
				cb.Save();
				g_version++;
				HWP::Log("gamekeys", m_action + (m_axis == 0 ? "" : " axis" + m_axis) + " bound to " + sc
					+ " (" + HWP::Options::KeyText(sc) + "), " + removed + " keyboard key(s) replaced; now " + Value());
			}
		}

		// bumped by every bind: the rows read the map again (the vanilla Controls window runs
		// only in the main menu, another level, where script globals start over)
		int g_version = 0;

		ControlMap@ Map()
		{
			auto cb = GetControlBindings();
			return cb is null ? null : cb.GetMap(MAP);
		}

		// the scancode of a single keyboard key binding; 0 for the mouse or a two-key chord
		int KeyboardScancode(ControlMapBinding@ b)
		{
			if (b is null || b.BoundControlType != ControllerType::Keyboard || b.BoundControlType2 == ControllerType::Keyboard)
				return 0;
			// the binding's id is the key's SDL name ("q", "lctrl"): resolved the way the
			// engine reads controls.cfg, so this does not lean on what BoundKey holds
			ControllerType type;
			int sc = Platform::ResolveInputKey(b.ID, type);
			if (type != ControllerType::Keyboard || sc < HWP::Options::SC_FIRST || sc > HWP::Options::SC_LAST)
				return 0;
			return sc;
		}

		// the rows, in the order the vanilla Controls window lists them
		array<string> g_ids;

		void Add(const string &in id, const string &in action, int axis = 0)
		{
			g_ids.insertLast(PREFIX + id);
			HWP::Options::Register(PREFIX + id, GameKeyOption(id, action, axis));
		}

		bool IsGameKey(const string &in optionId) { return optionId.findFirst(PREFIX) == 0; }

		// hwp-core's ctor (script globals reset every level)
		void Init()
		{
			g_ids.removeRange(0, g_ids.length());
			Add("move-up", "move_y", 1);
			Add("move-down", "move_y", 2);
			Add("move-left", "move_x", 1);
			Add("move-right", "move_x", 2);
			Add("skill1", "Skill1");
			Add("skill2", "Skill2");
			Add("skill3", "Skill3");
			Add("dash", "Dash");
			Add("potion", "Potion");
			Add("use", "Use");
			Add("playermenu", "PlayerMenu");
			Add("map", "PlayerMap");
			Add("guild", "GuildHall");
			Add("actionmenu", "ActionMenu");
			Add("overlay", "MapOverlay");
			Add("chat", "MenuChatAll");
			Add("menu-accept", "MenuAccept");
			Add("menu-forward", "MenuForward");
			Add("menu-context", "MenuContext");
			Add("menu-additional", "MenuAdditional");
			Add("menu-up", "MenuUp");
			Add("menu-down", "MenuDown");
			Add("menu-left", "MenuLeft");
			Add("menu-right", "MenuRight");
			Add("menu-nexttab", "MenuNextTab");
		}
	}
}
