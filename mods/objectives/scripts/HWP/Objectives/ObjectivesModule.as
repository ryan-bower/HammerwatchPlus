// Floor objectives (bugs 10.22.26 line 46): locked loot vaults and a sealed
// exit, on generated dungeon floors only (never boss floors or the town: they
// have no DungeonGenerator, Generation.as).
//
// - Vault: a small room sealed by a door nothing passes or shoots through
//   (doodads/hwp/objective_door.unit, "locked": solid, nav-blocking), with two
//   chests inside; a lever elsewhere on the floor (objective_switch.unit)
//   opens it. Both carry the map's info_poi icon until used. Setting
//   objectives.vaults 0-2 (default 1).
// - Exit: the floor's exits (WorldScript LevelExitAreaNext / AreaJump, LevelExitNext / Jump) are
//   disabled until the exit switch (objective_exit_switch.unit) is pressed.
//   The HUD says "Find the switch to open the way down", then "The way down
//   is open". Setting objectives.exit (default on).
//
// Host authority: the host generated the floor and knows every vault, door
// and switch (Generation.as). A switch use reaches the host through the
// vanilla use path (Units.as); the host broadcasts objectives.opened (kind,
// switch position, the door positions) and every machine flips the units it
// finds at those positions, plays the sound and updates the HUD. A joining
// client sends objectives.hello and gets objectives.state (every vault and
// the exit with their opened flags), applied the same way, silently.
//
// Logs: "[HWP:objectives] vault N opened by <name>", "exit opened by <name>",
// "exits sealed: N", "exits open: N", "state from host: ..." and the
// placement lines of Generation.as. hwp objectives prints the status; hwp
// objectives open (host, debug) opens everything on the floor.
namespace HWP
{
	namespace Objectives
	{
		const string KEY_VAULTS = "objectives.vaults";
		const string KEY_EXIT = "objectives.exit";
		const string EV_OPENED = "objectives.opened";
		const string EV_STATE = "objectives.state";
		const string RQ_HELLO = "objectives.hello";
		const float MATCH = 24.0f; // px: a unit is "at" a logged position within this
		const int EXIT_OPEN_SHOWN_MS = 6000;

		class Vault
		{
			ivec2 m_cell;
			ivec2 m_size;
			vec2 m_world;        // top-left of the room's cells
			int m_corridor;
			array<vec2> m_doors; // door unit positions
			ivec2 m_doorCell;
			ivec2 m_outDir;
			bool m_hasSwitch = false;
			ivec2 m_switchCell;
			vec2 m_switch;       // switch unit position
			bool m_opened = false;

			bool Contains(vec2 p)
			{
				return p.x >= m_world.x && p.y >= m_world.y && p.x < m_world.x + m_size.x * 16 && p.y < m_world.y + m_size.y * 16;
			}
		}

		// this floor; the host fills it in generation, a client from objectives.state
		array<Vault@> g_vaults;
		bool g_exitPresent = false;
		bool g_exitOpen = false;
		vec2 g_exitSwitch;
		bool g_sealed = false;
		int g_sealRetryMs = 0;     // host: the exit prefab's parts may fabricate after Start; retry the seal this long
		bool g_stateKnown = false; // a client: objectives.state arrived
		int g_vaultCount = 1;
		bool g_exitOn = true;
		int g_exitOpenShown = 0;
		HWPObjectivesHUD@ g_hud;
		array<HWPObjectiveDoor@> g_doors;
		array<HWPObjectiveSwitch@> g_switches;

		void RefreshSettings()
		{
			g_vaultCount = clamp(HWP::Settings::GetInt(KEY_VAULTS, 1), 0, 2);
			g_exitOn = HWP::Settings::GetBool(KEY_EXIT, true);
		}

		void ClearFloor()
		{
			g_vaults.removeRange(0, g_vaults.length());
			g_exitPresent = false;
			g_exitOpen = false;
			g_sealed = false;
			g_stateKnown = false;
			g_exitOpenShown = 0;
		}

		int OpenedVaults()
		{
			int n = 0;
			for (uint i = 0; i < g_vaults.length(); i++)
				if (g_vaults[i].m_opened)
					n++;
			return n;
		}

		// ---- units by position --------------------------------------------------

		HWPObjectiveSwitch@ SwitchAt(vec2 p)
		{
			for (uint i = 0; i < g_switches.length(); i++)
				if (g_switches[i].m_unit.IsValid() && dist(g_switches[i].Pos(), p) <= MATCH)
					return g_switches[i];
			return null;
		}

		HWPObjectiveDoor@ DoorAt(vec2 p)
		{
			for (uint i = 0; i < g_doors.length(); i++)
				if (g_doors[i].m_unit.IsValid() && dist(g_doors[i].Pos(), p) <= MATCH)
					return g_doors[i];
			return null;
		}

		int VaultOfSwitch(vec2 p)
		{
			for (uint i = 0; i < g_vaults.length(); i++)
				if (g_vaults[i].m_hasSwitch && dist(g_vaults[i].m_switch, p) <= MATCH)
					return int(i);
			return -1;
		}

		// ---- the exits ----------------------------------------------------------

		// the cave and citadel floors exit through the area scripts, the keep through a
		// LevelExitNext fired by a UseTrigger (prefabs/keep/level_exit_part_*.pfb); a
		// disabled world script does not execute (the vanilla ToggleScripts pattern)
		const array<string> EXIT_SCRIPTS = { "LevelExitAreaNext", "LevelExitAreaJump", "LevelExitNext", "LevelExitJump" };

		int SetExits(bool enabled)
		{
			int n = 0;
			for (uint t = 0; t < EXIT_SCRIPTS.length(); t++)
			{
				auto all = g_scene.FetchAllWorldScripts(EXIT_SCRIPTS[t]);
				for (uint i = 0; i < all.length(); i++)
				{
					all[i].SetEnabled(enabled);
					n++;
				}
			}
			return n;
		}

		void Seal()
		{
			if (g_sealed)
				return;
			g_sealed = true;
			int n = SetExits(false);
			HWP::Log("objectives", "exits sealed: " + n + " (switch at " + int(g_exitSwitch.x) + "," + int(g_exitSwitch.y) + ")");
			g_sealRetryMs = (n == 0 && Network::IsServer()) ? 3000 : 0;
			RefreshHUD();
		}

		void Unseal(bool quiet)
		{
			g_exitOpen = true;
			if (g_sealed)
			{
				g_sealed = false;
				int n = SetExits(true);
				HWP::Log("objectives", "exits open: " + n);
			}
			if (!quiet)
				g_exitOpenShown = EXIT_OPEN_SHOWN_MS;
			RefreshHUD();
		}

		// ---- host -----------------------------------------------------------------

		SValue@ OpenedData(const string &in kind, int index, vec2 sw, array<vec2>@ doors)
		{
			SValueBuilder b;
			b.PushDictionary();
			b.PushString("kind", kind);
			b.PushInteger("index", index);
			b.PushFloat("x", sw.x);
			b.PushFloat("y", sw.y);
			b.PushArray("doors");
			if (doors !is null)
				for (uint i = 0; i < doors.length(); i++)
				{
					b.PushDictionary();
					b.PushFloat("x", doors[i].x);
					b.PushFloat("y", doors[i].y);
					b.PopDictionary();
				}
			b.PopArray();
			b.PopDictionary();
			return b.Build();
		}

		string Who(PlayerBase@ player)
		{
			if (player is null || player.m_record is null)
				return "?";
			return player.m_record.GetName();
		}

		// Units.as: a switch was used on the host (its own player, or a client's NetUse)
		void HostSwitchUsed(HWPObjectiveSwitch@ sw, PlayerBase@ player)
		{
			if (!Network::IsServer())
				return;
			vec2 p = sw.Pos();
			if (sw.m_kind == "exit")
			{
				if (!g_exitPresent || dist(g_exitSwitch, p) > MATCH)
				{
					HWP::LogError("objectives", "exit switch used at " + int(p.x) + "," + int(p.y) + " but the floor's is at " + int(g_exitSwitch.x) + "," + int(g_exitSwitch.y));
					return;
				}
				if (g_exitOpen)
					return;
				HWP::Log("objectives", "exit opened by " + Who(player));
				HWP::Net::Broadcast(EV_OPENED, OpenedData("exit", -1, p, null));
				return;
			}
			int i = VaultOfSwitch(p);
			if (i < 0)
			{
				HWP::LogError("objectives", "vault switch used at " + int(p.x) + "," + int(p.y) + " matches no vault");
				return;
			}
			if (g_vaults[i].m_opened)
				return;
			HWP::Log("objectives", "vault " + i + " opened by " + Who(player));
			HWP::Net::Broadcast(EV_OPENED, OpenedData("vault", i, p, g_vaults[i].m_doors));
		}

		// hwp objectives open (host): everything on the floor, as if every switch was used
		void OpenAll()
		{
			for (uint i = 0; i < g_vaults.length(); i++)
				if (!g_vaults[i].m_opened)
				{
					HWP::Log("objectives", "vault " + i + " opened by command");
					HWP::Net::Broadcast(EV_OPENED, OpenedData("vault", int(i), g_vaults[i].m_switch, g_vaults[i].m_doors));
				}
			if (g_exitPresent && !g_exitOpen)
			{
				HWP::Log("objectives", "exit opened by command");
				HWP::Net::Broadcast(EV_OPENED, OpenedData("exit", -1, g_exitSwitch, null));
			}
		}

		SValue@ StateData()
		{
			SValueBuilder b;
			b.PushDictionary();
			b.PushArray("vaults");
			for (uint i = 0; i < g_vaults.length(); i++)
			{
				auto v = g_vaults[i];
				b.PushDictionary();
				b.PushFloat("x", v.m_world.x);
				b.PushFloat("y", v.m_world.y);
				b.PushInteger("w", v.m_size.x);
				b.PushInteger("h", v.m_size.y);
				b.PushBoolean("opened", v.m_opened);
				b.PushBoolean("has_switch", v.m_hasSwitch);
				b.PushFloat("sx", v.m_switch.x);
				b.PushFloat("sy", v.m_switch.y);
				b.PushArray("doors");
				for (uint d = 0; d < v.m_doors.length(); d++)
				{
					b.PushDictionary();
					b.PushFloat("x", v.m_doors[d].x);
					b.PushFloat("y", v.m_doors[d].y);
					b.PopDictionary();
				}
				b.PopArray();
				b.PopDictionary();
			}
			b.PopArray();
			b.PushBoolean("exit_present", g_exitPresent);
			b.PushBoolean("exit_open", g_exitOpen);
			b.PushFloat("ex", g_exitSwitch.x);
			b.PushFloat("ey", g_exitSwitch.y);
			b.PopDictionary();
			return b.Build();
		}

		void OnHello(uint8 peer, SValue@ data)
		{
			if (!Network::IsServer())
				return;
			HWP::Net::Send(peer, EV_STATE, StateData());
		}

		// ---- every machine --------------------------------------------------------

		array<vec2>@ ReadPoints(SValue@ arr)
		{
			array<vec2> pts;
			if (arr is null)
				return pts;
			auto items = arr.GetArray();
			for (uint i = 0; i < items.length(); i++)
				pts.insertLast(vec2(HWP::SV::Float(items[i], "x", 0), HWP::SV::Float(items[i], "y", 0)));
			return pts;
		}

		// flip the switch and open the doors at these positions; true when something was found
		int ApplyOpen(vec2 sw, array<vec2>@ doors, bool quiet)
		{
			int hit = 0;
			auto s = SwitchAt(sw);
			if (s !is null)
			{
				s.Flip();
				hit++;
			}
			for (uint i = 0; i < doors.length(); i++)
			{
				auto d = DoorAt(doors[i]);
				if (d !is null)
				{
					d.Open();
					hit++;
				}
			}
			if (!quiet)
				PlaySound2D(Resources::GetSoundEvent("event:/sfx/ui/quests/quest_complete"));
			return hit;
		}

		void OnOpened(SValue@ data)
		{
			if (data is null)
				return;
			string kind = HWP::SV::Str(data, "kind", "");
			vec2 sw(HWP::SV::Float(data, "x", 0), HWP::SV::Float(data, "y", 0));
			auto doors = ReadPoints(HWP::SV::Field(data, "doors"));
			if (kind == "exit")
			{
				g_exitPresent = true;
				int hit = ApplyOpen(sw, doors, false);
				Unseal(false);
				HWP::Log("objectives", "exit switch at " + int(sw.x) + "," + int(sw.y) + " flipped (" + hit + " unit(s) found); the way down is open");
				return;
			}
			int index = HWP::SV::Int(data, "index", -1);
			if (index >= 0 && index < int(g_vaults.length()))
				g_vaults[index].m_opened = true;
			int hit = ApplyOpen(sw, doors, false);
			auto hud = GetHUD();
			if (hud !is null)
				hud.AddAnnounce(Resources::GetString(".hwp.objectives.vault_open"), "hint_announce");
			RefreshHUD();
			HWP::Log("objectives", "vault " + index + " doors opened (" + hit + " unit(s) found of " + (doors.length() + 1) + ")");
		}

		// a client: the host's picture of the floor
		void OnState(SValue@ data)
		{
			if (data is null || Network::IsServer())
				return;
			g_vaults.removeRange(0, g_vaults.length());
			auto arr = HWP::SV::Field(data, "vaults");
			if (arr !is null)
			{
				auto items = arr.GetArray();
				for (uint i = 0; i < items.length(); i++)
				{
					Vault@ v = Vault();
					v.m_world = vec2(HWP::SV::Float(items[i], "x", 0), HWP::SV::Float(items[i], "y", 0));
					v.m_size = ivec2(HWP::SV::Int(items[i], "w", 9), HWP::SV::Int(items[i], "h", 8));
					v.m_opened = HWP::SV::Bool(items[i], "opened", false);
					v.m_hasSwitch = HWP::SV::Bool(items[i], "has_switch", false);
					v.m_switch = vec2(HWP::SV::Float(items[i], "sx", 0), HWP::SV::Float(items[i], "sy", 0));
					v.m_doors = ReadPoints(HWP::SV::Field(items[i], "doors"));
					g_vaults.insertLast(v);
					if (v.m_opened)
						ApplyOpen(v.m_switch, v.m_doors, true);
				}
			}
			g_exitPresent = HWP::SV::Bool(data, "exit_present", false);
			g_exitOpen = HWP::SV::Bool(data, "exit_open", false);
			g_exitSwitch = vec2(HWP::SV::Float(data, "ex", 0), HWP::SV::Float(data, "ey", 0));
			g_stateKnown = true;
			if (g_exitPresent && !g_exitOpen)
				Seal();
			else
				Unseal(true);
			HWP::Log("objectives", "state from host: " + g_vaults.length() + " vault(s), " + OpenedVaults() + " open, exit switch "
				+ (g_exitPresent ? (g_exitOpen ? "pressed" : "sealed") : "none"));
			RefreshHUD();
		}

		// ---- HUD, status ----------------------------------------------------------

		void RefreshHUD()
		{
			if (g_hud !is null)
				g_hud.Refresh(GetLocalPlayerRecord());
		}

		string ExitWord()
		{
			if (!g_exitPresent)
				return Resources::GetString(".hwp.objectives.exit_none");
			return Resources::GetString(g_exitOpen ? ".hwp.objectives.exit_opened" : ".hwp.objectives.exit_sealed");
		}

		string Status()
		{
			return Resources::GetString(".hwp.objectives.status", {
				{ "vaults", int(g_vaults.length()) }, { "open", OpenedVaults() }, { "exit", ExitWord() } });
		}

		void CmdObjectives(array<string>@ args)
		{
			if (args.length() > 0 && args[0] == "open")
			{
				if (!Network::IsServer())
				{
					HWP::Commands::Reply(Resources::GetString(".hwp.objectives.usage"));
					return;
				}
				OpenAll();
				HWP::Commands::Reply(Resources::GetString(".hwp.objectives.opened_all"));
				return;
			}
			if (args.length() > 0)
			{
				HWP::Commands::Reply(Resources::GetString(".hwp.objectives.usage"));
				return;
			}
			HWP::Commands::Reply(Status());
			for (uint i = 0; i < g_vaults.length(); i++)
			{
				auto v = g_vaults[i];
				HWP::Commands::Reply("vault " + i + ": world " + int(v.m_world.x) + "," + int(v.m_world.y) + " " + (v.m_size.x * 16) + "x" + (v.m_size.y * 16)
					+ ", switch " + (v.m_hasSwitch ? ("" + int(v.m_switch.x) + "," + int(v.m_switch.y)) : "none") + (v.m_opened ? ", open" : ", locked"));
			}
			if (g_exitPresent)
				HWP::Commands::Reply("exit switch: " + int(g_exitSwitch.x) + "," + int(g_exitSwitch.y) + (g_exitOpen ? ", pressed" : ", not yet"));
			HWP::Log("objectives", "status: " + Status());
		}

		void OnSettingChanged(const string &in key)
		{
			if (key.findFirst("objectives.") == 0)
				RefreshSettings();
		}

		void Tick(int ms)
		{
			if (g_sealRetryMs > 0)
			{
				// a PrefabPicker exit (the keep's level_exit.pfb) fabricates its part after
				// the module's Start: seal again until the scripts are there
				g_sealRetryMs -= ms;
				if (!g_sealed)
					g_sealRetryMs = 0;
				else
				{
					int n = SetExits(false);
					if (n > 0)
					{
						HWP::Log("objectives", "exits sealed: " + n + " (switch at " + int(g_exitSwitch.x) + "," + int(g_exitSwitch.y) + ")");
						HWP::Log("objectives", "exits sealed after start: the exit part fabricated later");
						g_sealRetryMs = 0;
					}
					else if (g_sealRetryMs <= 0)
						HWP::LogError("objectives", "exits sealed: none found on this floor (" + EXIT_SCRIPTS.length() + " script types)");
				}
			}
			if (g_exitOpenShown > 0)
			{
				g_exitOpenShown -= ms;
				if (g_exitOpenShown <= 0)
				{
					g_exitOpenShown = 0;
					RefreshHUD();
				}
			}
		}
	}
}

// One line under the region banner: the exit objective; a second with the
// vault count. Hidden when the floor has neither.
class HWPObjectivesHUD : HUDComponent
{
	TextWidget@ m_line;
	TextWidget@ m_vaults;

	HWPObjectivesHUD(GUIBuilder@ b)
	{
		super(b, "gui/hwp_objectives.gui");
		@m_line = cast<TextWidget>(m_widget.GetWidgetById("hwp-objective"));
		@m_vaults = cast<TextWidget>(m_widget.GetWidgetById("hwp-objective-vaults"));
		m_visible = false;
	}

	void Refresh(PlayerRecord@ record) override
	{
		string line = "";
		if (HWP::Objectives::g_exitPresent)
		{
			if (!HWP::Objectives::g_exitOpen)
				line = Resources::GetString(".hwp.objectives.exit_find");
			else if (HWP::Objectives::g_exitOpenShown > 0)
				line = Resources::GetString(".hwp.objectives.exit_open");
		}
		string vaults = "";
		int total = int(HWP::Objectives::g_vaults.length());
		if (total > 0)
			vaults = Resources::GetString(".hwp.objectives.vaults", { { "open", HWP::Objectives::OpenedVaults() }, { "total", total } });
		if (m_line !is null)
			m_line.SetText(line);
		if (m_vaults !is null)
			m_vaults.SetText(vaults);
		m_visible = !line.isEmpty() || !vaults.isEmpty();
		Invalidate();
	}
}

namespace HWPObjectives
{
	[Hook]
	void HUDConstructor(HUD@ hud, GUIBuilder@ b)
	{
		auto comp = HWPObjectivesHUD(b);
		hud.m_components.insertLast(comp);
		@HWP::Objectives::g_hud = comp;
		comp.Refresh(GetLocalPlayerRecord());
	}
}

namespace Modules
{
	class HWPObjectivesModule : Module, HWP::ModuleStart
	{
		HWPObjectivesModule()
		{
			super("hwp-objectives");
			// script globals reset with every level: the unit registries fill as the
			// level's units construct, the floor record in generation (host) or from
			// objectives.state (client)
			HWP::Objectives::ClearFloor();
			HWP::Settings::Sync("objectives.");
			HWP::Objectives::RefreshSettings();
			int n = HWP::Objectives::Gen::Install();
			if (n > 0)
				HWP::Log("objectives", "generator command on " + n + " indoor floor(s)");
			HWP::Net::OnRequest(HWP::Objectives::RQ_HELLO, HWP::Net::RequestHandler(HWP::Objectives::OnHello));
			HWP::Net::OnEvent(HWP::Objectives::EV_OPENED, HWP::Net::EventHandler(HWP::Objectives::OnOpened));
			HWP::Net::OnEvent(HWP::Objectives::EV_STATE, HWP::Net::EventHandler(HWP::Objectives::OnState));
			HWP::Commands::Register("objectives", "[open]  this floor's vaults and exit switch (open: host debug, opens all)", HWP::Commands::Handler(HWP::Objectives::CmdObjectives));
			HWP::Commands::OnSettingChanged(HWP::Commands::SettingListener(HWP::Objectives::OnSettingChanged));
		}

		void Start(StartMode sMode)
		{
			HWP::Objectives::RefreshSettings();
			if (Network::IsServer())
			{
				if (HWP::Objectives::g_exitPresent && !HWP::Objectives::g_exitOpen)
					HWP::Objectives::Seal();
				HWP::Log("objectives", "start: " + HWP::Objectives::g_vaults.length() + " vault(s), exit switch "
					+ (HWP::Objectives::g_exitPresent ? "sealed" : "none") + ", " + HWP::Objectives::g_doors.length() + " door unit(s), "
					+ HWP::Objectives::g_switches.length() + " switch unit(s)");
			}
			else
				HWP::Net::Request(HWP::Objectives::RQ_HELLO);
			HWP::Objectives::RefreshHUD();
		}

		// HWP::Guard (tools/guard_modules.py): a script error here turns this off, not the game
		HWP::Guard m_guardUpdateFrame;
		void UpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused) override
		{
			if (m_guardUpdateFrame.Skip("objectives", "HWPObjectivesModule.UpdateFrame"))
				return;
			if (m_guardUpdateFrame.Raw())
			{
				GuardedUpdateFrame(ms, gameInput, menuInput, paused);
				m_guardUpdateFrame.Ok();
				return;
			}
			try { GuardedUpdateFrame(ms, gameInput, menuInput, paused); m_guardUpdateFrame.Ok(); }
			catch { m_guardUpdateFrame.Failed(); }
		}

		void GuardedUpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused)
		{
			if (paused)
				return;
			HWP::Objectives::Tick(ms);
		}
	}
}
