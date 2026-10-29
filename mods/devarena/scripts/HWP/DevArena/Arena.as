// Dev Arena: the Arena tab (docs/devarena/SPEC.md, Arena, Q26). The floor is a seeded vanilla
// floor started by gamelab-hands' `mission`; its normal mobs are the targets.
//
// Reset (F3) heals the player, fills mana, resets cooldowns, kills what the brush spawned and
// resets the golem (Golem.as); the floor stays. Reload floor re-runs the same mission floor
// with the same generation seed (GameLab::g_genSeed, Hands.as) and the NG+ picked here.
//
// Me: god, no-cd and speed are the engine's own cheat flags (CVars::ChtGodmode,
// ChtNoCooldowns, ChtSpeed: Console/Cheats.as:291-294, 108-109; read at Player.as:384, :1506,
// :1408); inf mana is the cht_plr_free_mana_cost cvar (Player.as:742, :778). Boons are
// PlayerRecord.SetStat, what cht_boon_lvl does (Cheats.as:195-218).
//
// Mobs: freeze (Freeze.as); unkillable tops every mob's hp ratio up each frame, so damage is
// still dealt and shown and only a hit larger than a full bar kills; passive turns targeting
// off and drops the target each frame (m_props.m_targeting, CompositeActorBehavior.as:243).
//
// Brush: arm a unit and an encounter size, then middle-click places it at the mouse's world
// position (ToWorldspace, Modules/PlayerMeasure.as:33); Esc disarms. A placed encounter is
// timed from placement until its last unit dies: clear time, damage taken, deaths.
namespace HWP
{
namespace DevArena
{
	// the arena hotkeys' defaults (rebindable: Dock.as, HotkeyOption)
	const int SCANCODE_F3 = 60;
	const int SCANCODE_F4 = 61;
	const int SCANCODE_F6 = 63;
	const int MOUSE_MIDDLE = 2;      // SDL_BUTTON_MIDDLE (assumed: no script reads a mouse button)

	// brush units: the barracks guards (themes_barracks.sval) and a few undead regulars
	const array<string> BRUSH_UNITS = {
		"actors/undead/guard/guard_footman.unit", "actors/undead/guard/guard_defender.unit",
		"actors/undead/guard/guard_sentry.unit", "actors/undead/guard/guard_mage.unit",
		"actors/undead/guard/guard_knight.unit", "actors/undead/guard/guard_footman_elite.unit",
		"actors/undead/guard/guard_defender_elite.unit", "actors/undead/guard/guard_sentry_elite.unit",
		"actors/undead/horde/horde_crawler.unit", "actors/undead/horde/horde_necromancer.unit",
		"actors/undead/court/court_doomsayer.unit" };
	const array<string> ENC_KINDS = { "single", "pack", "swarm" };
	const array<int> ENC_SIZES = { 1, 4, 13 };
	const array<string> BOONS = { "valor", "hunt", "arcane", "avarice", "benevolence" };

	// me
	bool g_god;
	bool g_noCd;
	bool g_infMana;
	float g_speed = 1.0f;
	array<int> g_boon = { -1, -1, -1, -1, -1 };     // -1: not set here

	// mobs
	bool g_unkillable;
	bool g_passive;

	// floor
	string g_arenaLevel;             // the level this state belongs to ("" none yet)
	vec2 g_arenaStart;               // the player's first position on it
	int g_arenaNgp = -1;             // NG+ for the next Reload (-1: the current g_ngp)
	int g_resets;
	int g_reloads;
	bool g_paused;                   // F6
	// Reload waits for the click's release: a level change in the middle of a press left
	// MenuInput.Forward.Pressed set for good, and the dock, open again on the new floor, took
	// it as another Reload, every floor (arena-dock 20261020-235104: 3 reloads a second)
	const int RELOAD_DELAY = 10;     // frames
	int g_reloadIn = -1;
	const int CLICK_GUARD = 10;      // frames on a new floor with dock clicks ignored, a held press cleared
	int g_clickGuard;

	// brush
	int g_brushUnit = -1;            // BRUSH_UNITS index, -1 disarmed
	int g_brushKind;                 // ENC_KINDS index
	bool g_midWas;
	int g_ptrMiddleSeen;             // GameLab::g_ptrMiddlePress last seen
	int g_placed;
	array<UnitPtr> g_spawned;        // everything the brush made

	class Encounter
	{
		int n;
		string kind;
		string unit;
		array<UnitPtr> units;
		int startMs;
		float hpLost0;
		int deaths0;
		int clearMs = -1;
		float taken;
		int deaths;
	}
	array<Encounter@> g_encounters;  // newest last
	int g_deaths;
	bool g_wasDead;

	string ShortUnit(const string &in path)
	{
		int s = path.findLast("/");
		string f = s < 0 ? path : path.substr(s + 1);
		return f.findLast(".unit") > 0 ? f.substr(0, f.findLast(".unit")) : f;
	}

	string LevelKey()
	{
		return GetCurrentLevelFilename() + "#" + GameLab::g_genSeed;
	}

	// ---- me ---------------------------------------------------------------------------
	void SetMe(const string &in what, bool on)
	{
		if (what == "god")
		{
			g_god = on;
			CVars::ChtGodmode = on;
		}
		else if (what == "nocd")
		{
			g_noCd = on;
			CVars::ChtNoCooldowns = on;
		}
		else if (what == "mana")
		{
			g_infMana = on;
			SetVar("e_cheats", true);
			SetVar("cht_plr_free_mana_cost", on);
		}
		HWP::Log("devarena", "arena me " + what + " " + (on ? "on" : "off"));
		g_lastAction = what + " " + (on ? "on" : "off");
	}

	void SetSpeed(float s)
	{
		g_speed = s;
		CVars::ChtSpeed = s;
		HWP::Log("devarena", "arena me speed " + s);
		g_lastAction = "speed x" + s;
	}

	void SetBoon(int i, int lvl)
	{
		auto rec = GetLocalPlayerRecord();
		if (rec is null || i < 0 || i >= int(BOONS.length()))
			return;
		lvl = max(0, min(lvl, 10));
		auto s = Modifiers::ParseStat(BOONS[i]);
		if (s == Modifiers::ConvertableStat::Num)
			return;
		rec.SetStat(s, lvl);
		g_boon[i] = lvl;
		HWP::Log("devarena", "arena boon " + BOONS[i] + " " + lvl);
		g_lastAction = "boon " + BOONS[i] + " " + lvl;
	}

	// ---- floor ------------------------------------------------------------------------
	void KillSpawned()
	{
		for (uint i = 0; i < g_spawned.length(); i++)
		{
			if (!g_spawned[i].IsValid())
				continue;
			auto a = cast<Actor>(g_spawned[i].GetScriptBehavior());
			if (a !is null && !a.IsDead())
				a.Kill(null, 0);
		}
		g_spawned.resize(0);
	}

	// F3
	void ArenaReset()
	{
		auto plr = LocalPlayer();
		if (plr !is null)
		{
			plr.m_record.ResetPlayerHealthMana();
			for (uint i = 0; i < plr.m_skills.length(); i++)
				plr.m_skills[i].ResetCooldown();
		}
		KillSpawned();
		g_encounters.resize(0);
		GolemReset();
		g_resets++;
		HWP::Log("devarena", "arena reset " + g_resets);
		g_lastAction = "reset (" + KeyLabel(KeyReset()) + ")";
	}

	void ReloadFloor()
	{
		auto mm = MissionManager::g_module;
		auto def = mm is null ? null : MissionDef::Get(mm.m_missionDefHash);
		if (def is null)
		{
			g_lastError = "reload: no mission running";
			return;
		}
		int floor = int(mm.m_missionLevelIndex);
		if (g_arenaNgp >= 0)
		{
			auto rec = GetLocalPlayerRecord();
			int cap = rec is null ? 0 : rec.ngp;
			g_ngp = float(max(0, min(cap, g_arenaNgp)));
		}
		// the floor regenerates from the same seed (Hands.as g_genSeed: the town save carries it)
		GameLab::g_genSeedPending = GameLab::g_genSeed != 0;
		g_reloads++;
		HWP::Log("devarena", "arena reload floor " + floor + " seed " + GameLab::g_genSeed + " ngp " + int(g_ngp + 0.5f));
		g_lastAction = "reload floor";
		g_arenaLevel = "";
		mm.SetMission(mm.m_missionDefHash, randi());
		mm.m_missionLevelIndex = floor;
		mm.StartMission();
	}

	int CullAll()
	{
		int n = 0;
		auto enemies = g_scene.FetchAllActorsWithOtherTeam(g_team_player);
		for (uint i = 0; i < enemies.length(); i++)
		{
			auto a = cast<Actor>(enemies[i].GetScriptBehavior());
			if (a !is null && a.IsTargetable() && !a.IsDead() && !IsGolem(enemies[i]))
			{
				a.Kill(null, 0);
				n++;
			}
		}
		HWP::Log("devarena", "arena cull " + n);
		g_lastAction = "cull " + n;
		return n;
	}

	void TogglePause()
	{
		g_paused = !IsPaused();
		PauseGame(g_paused, true);
		HWP::Log("devarena", "arena pause " + (g_paused ? "on" : "off"));
		g_lastAction = (g_paused ? "paused (" : "unpaused (") + KeyLabel(KeyPause()) + ")";
	}

	// ---- brush ------------------------------------------------------------------------
	void Arm(int unit, int kind)
	{
		g_brushUnit = unit;
		if (kind >= 0)
			g_brushKind = kind;
		HWP::Log("devarena", unit < 0 ? "brush disarmed"
			: "brush armed " + ShortUnit(BRUSH_UNITS[unit]) + " " + ENC_KINDS[g_brushKind]);
		g_lastAction = unit < 0 ? "brush off" : "brush " + ShortUnit(BRUSH_UNITS[unit]) + " x" + ENC_SIZES[g_brushKind] + ": middle-click";
	}

	// Esc with the brush armed disarms it and nothing else. The engine hands Esc to
	// g_gameMode.MenuBack(), whose HUD asks each component first (HUD.as:538-547, then
	// HWR2GameMode.as:429-441), and the pause menu opens when none takes it (arena-dock
	// 20261020-235519: a key press alone disarmed and opened the menu). A drawless component
	// at the head of the HUD's list takes it while armed.
	class EscGuard : ::HUDComponent
	{
		EscGuard() { super(null, ""); m_visible = false; }
		void Update(int dt, PlayerRecord@ record) override {}
		void Draw(SpriteBatch& sb, int idt) override {}
		void DoLayout() override {}
		bool MenuBack() override
		{
			if (g_brushUnit < 0)
				return false;
			g_hotkeys++;
			Arm(-1, -1);
			return true;
		}
	}
	EscGuard@ g_escGuard;

	void InstallEscGuard()
	{
		auto gm = cast<AGameplayGameMode>(g_gameMode);
		if (gm is null || gm.m_hud is null)
			return;
		if (g_escGuard is null)
			@g_escGuard = EscGuard();
		if (gm.m_hud.m_components.findByRef(g_escGuard) < 0)
			gm.m_hud.m_components.insertAt(0, g_escGuard);
	}

	// n units in a ring around p (one in the middle for a single)
	int Place(vec2 p)
	{
		if (g_brushUnit < 0)
			return 0;
		string file = BRUSH_UNITS[g_brushUnit];
		auto prod = Resources::GetUnitProducer(file);
		if (prod is null)
		{
			g_lastError = "no unit " + file;
			return 0;
		}
		Encounter e;
		e.n = ENC_SIZES[g_brushKind];
		e.kind = ENC_KINDS[g_brushKind];
		e.unit = ShortUnit(file);
		e.startMs = g_clock;
		e.hpLost0 = g_hpLost;
		e.deaths0 = g_deaths;
		float z = 0;
		auto plr = LocalPlayer();
		if (plr !is null)
			z = plr.m_unit.GetPosition().z;
		for (int i = 0; i < e.n; i++)
		{
			vec2 at = p;
			if (e.n > 1)
			{
				float ang = 6.2831853f * float(i) / float(e.n);
				float rad = e.n > 4 ? (i % 2 == 0 ? 40.0f : 22.0f) : 24.0f;
				at += vec2(cos(ang), sin(ang)) * rad;
			}
			UnitPtr u = prod.Produce(g_scene, vec3(at.x, at.y, z));
			if (!u.IsValid())
				continue;
			e.units.insertLast(u);
			g_spawned.insertLast(u);
			auto c = cast<CompositeActorBehavior>(u.GetScriptBehavior());
			if (c !is null && plr !is null && !g_passive && !g_freeze)
				c.SetTarget(plr, 1.0f, true);     // brought to fight, not to stand guard
		}
		g_encounters.insertLast(e);
		if (g_encounters.length() > 8)
			g_encounters.removeAt(0);
		g_placed++;
		HWP::Log("devarena", "brush placed " + e.unit + " " + e.kind + " " + e.units.length() + " at " + int(p.x) + "," + int(p.y));
		g_lastAction = "placed " + e.units.length() + " " + e.unit;
		return e.units.length();
	}

	// a middle press this frame, at window pixel `at`
	bool MiddlePressed(vec2 &out at)
	{
		auto gm = cast<BaseGameMode>(g_gameMode);
		at = gm is null ? vec2() : gm.GetMousePos();
		bool down = Platform::IsKeyDown(ControllerType::Mouse, 0, MOUSE_MIDDLE);
		bool was = g_midWas;
		g_midWas = down;
		// GameLab's emulated mouse (gamelab-hands `pointer <x> <y> mclick`) counts presses
		if (GameLab::g_ptrMiddlePress != g_ptrMiddleSeen)
		{
			g_ptrMiddleSeen = GameLab::g_ptrMiddlePress;
			at = GameLab::g_ptrMiddleAt;
			return true;
		}
		return down && !was;
	}

	// ---- frame ------------------------------------------------------------------------
	void TickArenaKeys()
	{
		bool f3 = KeyPressed(KeyReset());
		bool f4 = KeyPressed(KeyGolem());
		bool f6 = KeyPressed(KeyPause());
		vec2 midAt;
		bool mid = MiddlePressed(midAt);
		InstallEscGuard();     // Esc: EscGuard.MenuBack
		if (g_typing || TextInputBusy())
			return;
		if (f3) { g_hotkeys++; ArenaReset(); }
		if (f4) { g_hotkeys++; GolemRoomToggle(); }
		if (f6) { g_hotkeys++; TogglePause(); }
		if (mid && g_brushUnit >= 0 && !(g_dockOpen && Inside(DockRect(), midAt / g_gameMode.m_wndScale)) && LocalPlayer() !is null)
			Place(xy(ToWorldspace(midAt)));
	}

	void TickArena(int ms, bool paused)
	{
		auto plr = LocalPlayer();
		if (plr is null)
			return;
		if (g_reloadIn >= 0 && g_reloadIn-- == 0)
		{
			ReloadFloor();
			return;
		}
		string key = LevelKey();
		if (key != g_arenaLevel)
		{
			// a new floor: what was spawned, timed or placed is gone with the old one
			g_arenaLevel = key;
			g_clickGuard = CLICK_GUARD;
			g_arenaStart = xy(plr.m_unit.GetPosition());
			g_spawned.resize(0);
			g_encounters.resize(0);
			GolemNewLevel();
			BenchNewLevel();
			ApplyCheats();     // CVars::Cht* reset with the level; ours came back in the town save
			HWP::Log("devarena", "arena floor " + GetCurrentLevelFilename() + " seed " + GameLab::g_genSeed
				+ " ngp " + int(g_ngp + 0.5f) + " start " + int(g_arenaStart.x) + "," + int(g_arenaStart.y));
		}
		if (paused)
			return;

		bool dead = plr.IsDead();
		if (dead && !g_wasDead)
			g_deaths++;
		g_wasDead = dead;

		if (g_unkillable || g_passive)
		{
			auto mobs = Mobs();
			for (uint i = 0; i < mobs.length(); i++)
			{
				if (IsGolem(mobs[i].m_unit))
					continue;
				if (g_unkillable)
					mobs[i].m_hp = 1.0f;
				if (g_passive)
				{
					mobs[i].m_props.m_targeting = false;
					@mobs[i].m_target = null;
				}
			}
		}

		for (uint i = 0; i < g_encounters.length(); i++)
		{
			auto e = g_encounters[i];
			if (e.clearMs >= 0)
				continue;
			bool alive = false;
			for (uint k = 0; k < e.units.length() && !alive; k++)
			{
				auto a = e.units[k].IsValid() ? cast<Actor>(e.units[k].GetScriptBehavior()) : null;
				alive = a !is null && !a.IsDead();
			}
			e.taken = g_hpLost - e.hpLost0;
			e.deaths = g_deaths - e.deaths0;
			if (!alive)
			{
				e.clearMs = g_clock - e.startMs;
				HWP::Log("devarena", "encounter " + e.kind + " " + e.unit + " x" + e.units.length() + " clear "
					+ e.clearMs + " ms taken " + int(e.taken * 1000) / 1000.0f + " deaths " + e.deaths);
			}
		}
	}

	void SetPassive(bool on)
	{
		g_passive = on;
		if (!on)
		{
			auto mobs = Mobs();
			for (uint i = 0; i < mobs.length(); i++)
				if (!IsGolem(mobs[i].m_unit))
					mobs[i].m_props.m_targeting = true;
		}
		HWP::Log("devarena", "arena passive " + (on ? "on" : "off"));
	}

	// ---- layout -----------------------------------------------------------------------
	string OnOff(bool on, const string &in label)
	{
		return (on ? "[x] " : "[ ] ") + label;
	}

	float Head(Ui@ ui, float x, float y, const string &in s)
	{
		ui.Text(x, y, s, COL_HEAD);
		return y + RowH();
	}

	float LayoutArena(Ui@ ui, float x, float y, float w)
	{
		float row = RowH();
		float gap = 2;

		y = Head(ui, x, y, "FLOOR");
		auto mm = MissionManager::g_module;
		string lvl = GetCurrentLevelFilename();
		ui.Text(x, y, ShortUnit(lvl) + "  floor " + (mm is null ? -1 : int(mm.m_missionLevelIndex))
			+ "  seed " + GameLab::g_genSeed + "  NG+" + int(g_ngp + 0.5f), COL_DIM);
		y += row;
		float bw = (w - gap * 3) / 4;
		if (ui.Button("reset", vec4(x, y, bw, row), "Reset " + ShortKeyLabel(KeyReset())))
			ArenaReset();
		if (ui.Button("reload", vec4(x + (bw + gap), y, bw, row), g_reloadIn >= 0 ? "Reloading" : "Reload"))
			g_reloadIn = RELOAD_DELAY;
		if (ui.Button("cull", vec4(x + (bw + gap) * 2, y, bw, row), "Cull"))
			CullAll();
		if (ui.Button("pause", vec4(x + (bw + gap) * 3, y, bw, row), (IsPaused() ? "Resume " : "Pause ") + ShortKeyLabel(KeyPause()), IsPaused() ? COL_ON : COL_BUTTON))
			TogglePause();
		y += row + gap;
		int ngp = g_arenaNgp >= 0 ? g_arenaNgp : int(g_ngp + 0.5f);
		if (ui.Button("ngp|-", vec4(x, y, row * 1.5f, row), "-"))
			g_arenaNgp = max(0, ngp - 1);
		ui.Text(x + row * 1.5f + 4, y + 1, "NG+" + ngp + (ngp != int(g_ngp + 0.5f) ? " (on Reload)" : ""));
		if (ui.Button("ngp|+", vec4(x + w * 0.5f, y, row * 1.5f, row), "+"))
		{
			auto rec = GetLocalPlayerRecord();
			g_arenaNgp = min(rec is null ? 0 : rec.ngp, ngp + 1);
		}
		y += row + PAD;

		y = Head(ui, x, y, "MOBS");
		float hw = (w - gap * 2) / 3;
		if (ui.Button("freeze", vec4(x, y, hw, row), OnOff(g_freeze, "freeze"), g_freeze ? COL_ON : COL_BUTTON))
			SetFreeze(!g_freeze);
		if (ui.Button("unkillable", vec4(x + hw + gap, y, hw, row), OnOff(g_unkillable, "unkillable"), g_unkillable ? COL_ON : COL_BUTTON))
		{
			g_unkillable = !g_unkillable;
			HWP::Log("devarena", "arena unkillable " + (g_unkillable ? "on" : "off"));
		}
		if (ui.Button("passive", vec4(x + (hw + gap) * 2, y, hw, row), OnOff(g_passive, "passive"), g_passive ? COL_ON : COL_BUTTON))
			SetPassive(!g_passive);
		y += row + PAD;

		y = Head(ui, x, y, "ME");
		float qw = (w - gap * 2) / 3;
		if (ui.Button("me|god", vec4(x, y, qw, row), OnOff(g_god, "god"), g_god ? COL_ON : COL_BUTTON))
			SetMe("god", !g_god);
		if (ui.Button("me|nocd", vec4(x + qw + gap, y, qw, row), OnOff(g_noCd, "no-cd"), g_noCd ? COL_ON : COL_BUTTON))
			SetMe("nocd", !g_noCd);
		if (ui.Button("me|mana", vec4(x + (qw + gap) * 2, y, qw, row), OnOff(g_infMana, "inf mana"), g_infMana ? COL_ON : COL_BUTTON))
			SetMe("mana", !g_infMana);
		y += row + gap;
		ui.Text(x, y + 1, "speed", COL_DIM);
		array<float> speeds = { 1.0f, 1.5f, 2.0f, 4.0f };
		float sx = x + ui.TextW("speed ") + 4;
		for (uint i = 0; i < speeds.length(); i++)
		{
			string l = "x" + speeds[i];
			float cw = ui.TextW(l) + 6;
			if (ui.Button("speed|" + speeds[i], vec4(sx, y, cw, row), l, abs(g_speed - speeds[i]) < 0.01f ? COL_ON : COL_BUTTON))
				SetSpeed(speeds[i]);
			sx += cw + gap;
		}
		y += row + gap;
		for (uint i = 0; i < BOONS.length(); i++)
		{
			ui.Text(x, y + 1, BOONS[i], COL_DIM);
			float bx = x + w * 0.45f;
			if (ui.Button("boon|" + BOONS[i] + "|-", vec4(bx, y, row * 1.5f, row), "-"))
				SetBoon(i, max(0, g_boon[i]) - 1);
			ui.Text(bx + row * 1.5f + 4, y + 1, g_boon[i] < 0 ? "-" : "" + g_boon[i]);
			if (ui.Button("boon|" + BOONS[i] + "|+", vec4(bx + row * 3.5f, y, row * 1.5f, row), "+"))
				SetBoon(i, max(0, g_boon[i]) + 1);
			y += row;
		}
		y += PAD;

		y = Head(ui, x, y, "BRUSH  (middle-click places, Esc disarms)");
		float kx = x;
		for (uint i = 0; i < ENC_KINDS.length(); i++)
		{
			string l = ENC_KINDS[i] + " " + ENC_SIZES[i];
			float cw = ui.TextW(l) + 6;
			if (ui.Button("enc|" + ENC_KINDS[i], vec4(kx, y, cw, row), l, g_brushKind == int(i) ? COL_ON : COL_BUTTON))
			{
				g_brushKind = i;
				if (g_brushUnit >= 0)
					Arm(g_brushUnit, i);
			}
			kx += cw + gap;
		}
		if (g_brushUnit >= 0 && ui.Button("disarm", vec4(x + w - ui.TextW("disarm") - 6, y, ui.TextW("disarm") + 6, row), "disarm"))
			Arm(-1, -1);
		y += row + gap;
		float uw = (w - gap) / 2;
		for (uint i = 0; i < BRUSH_UNITS.length(); i++)
		{
			string n = ShortUnit(BRUSH_UNITS[i]);
			float ux = x + (i % 2 == 0 ? 0 : uw + gap);
			if (ui.Button("brush|" + n, vec4(ux, y, uw, row), n, g_brushUnit == int(i) ? COL_ON : COL_BUTTON))
				Arm(g_brushUnit == int(i) ? -1 : int(i), -1);
			if (i % 2 == 1 || i == BRUSH_UNITS.length() - 1)
				y += row + 1;
		}
		y += PAD;

		y = Head(ui, x, y, "ENCOUNTERS");
		if (g_encounters.length() == 0)
		{
			ui.Text(x, y, "none placed", COL_DIM);
			y += row;
		}
		for (int i = int(g_encounters.length()) - 1; i >= 0; i--)
		{
			auto e = g_encounters[i];
			string t = e.clearMs >= 0 ? formatFloat(e.clearMs / 1000.0f, "", 0, 1) + "s" : formatFloat((g_clock - e.startMs) / 1000.0f, "", 0, 1) + "s...";
			ui.Text(x, y, e.kind + " " + e.unit + " x" + e.units.length() + "  " + t + "  taken " + int(e.taken)
				+ "  deaths " + e.deaths, e.clearMs >= 0 ? COL_TEXT : COL_SUB);
			y += row;
		}
		return y + PAD;
	}

	// a JSON array of the encounters, oldest first
	string EncountersJson()
	{
		array<string> rows;
		for (uint i = 0; i < g_encounters.length(); i++)
		{
			auto e = g_encounters[i];
			rows.insertLast("{\"kind\":" + GameLab::Quote(e.kind) + ",\"unit\":" + GameLab::Quote(e.unit) + ",\"n\":" + e.units.length()
				+ ",\"clearMs\":" + e.clearMs + ",\"taken\":" + e.taken + ",\"deaths\":" + e.deaths + "}");
		}
		return GameLab::RawArray(rows);
	}

	// da-arena: read-only. The Arena and Golem tabs: the floor (level, mission floor index,
	// generation seed, g_ngp, the NG+ picked for Reload, the room centre = the player's start),
	// resets / reloads / pause, the mob toggles, the cheat flags as set here and as the engine
	// holds them (CVars::Cht*), boons set here, the brush (armed unit, encounter kind, placed,
	// mobs it spawned alive), encounters (newest 8: kind, unit, n, clearMs (-1 running), hp
	// taken, deaths), player deaths, whether the town save carried the state, and the golem
	// (profile, NG+, pool, alive, hp, armor/res as a hit sees them, inRoom, culled, pull state,
	// last pull json); walls = wall pieces up, inBox = the player inside the walled box, atWall = the wall they are against.
	void VerbArena(const string &in id, array<string>@ args)
	{
		auto mm = MissionManager::g_module;
		int alive = 0;
		for (uint i = 0; i < g_spawned.length(); i++)
		{
			auto a = g_spawned[i].IsValid() ? cast<Actor>(g_spawned[i].GetScriptBehavior()) : null;
			if (a !is null && !a.IsDead())
				alive++;
		}
		array<string> boons;
		for (uint i = 0; i < BOONS.length(); i++)
			boons.insertLast(GameLab::Quote(BOONS[i]) + ":" + g_boon[i]);
		auto plrNow = LocalPlayer();
		vec3 plrAt = plrNow is null ? vec3() : plrNow.m_unit.GetPosition();
		GameLab::Emit(GameLab::Reply(id, true).Str("level", GetCurrentLevelFilename())
			.Int("floor", mm is null ? -1 : int(mm.m_missionLevelIndex)).Int("seed", GameLab::g_genSeed)
			.Int("ngp", int(g_ngp + 0.5f)).Int("reloadNgp", g_arenaNgp)
			.Num("startX", g_arenaStart.x).Num("startY", g_arenaStart.y)
			.Int("resets", g_resets).Int("reloads", g_reloads).Bool("paused", IsPaused())
			.Bool("freeze", g_freeze).Bool("unkillable", g_unkillable).Bool("passive", g_passive)
			.Bool("god", g_god).Bool("nocd", g_noCd).Bool("mana", g_infMana).Num("speed", g_speed)
			.Bool("cvarGod", CVars::ChtGodmode).Bool("cvarNocd", CVars::ChtNoCooldowns).Num("cvarSpeed", CVars::ChtSpeed)
			.Raw("boons", "{" + join(boons, ",") + "}")
			.Str("brush", g_brushUnit < 0 ? "" : ShortUnit(BRUSH_UNITS[g_brushUnit])).Str("kind", ENC_KINDS[g_brushKind])
			.Int("placed", g_placed).Int("spawnedAlive", alive).Raw("encounters", EncountersJson())
			.Int("deaths", g_deaths).Bool("restored", g_arenaLoaded).Int("hotkeys", g_hotkeys)
			.Str("lastAction", g_lastAction).Str("lastError", g_lastError)
			.Num("x", plrAt.x).Num("y", plrAt.y).Bool("rlPending", g_rlPending).Int("rlStage", g_rlStage).Num("rlDist", RelaunchDist())
			.Int("relaunches", g_relaunches).Str("preset", g_preset)
			.Int("walls", g_walls.length()).Bool("inBox", PlayerInBox()).Str("atWall", PlayerAtWall()).Raw("fromRoom", PlayerFromRoom())
			.Raw("golem", GolemJson()));
	}
}
}
