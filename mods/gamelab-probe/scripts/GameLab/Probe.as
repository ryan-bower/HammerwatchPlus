// gamelab-probe: GameLab's command channel and read-only state probes.
//
// The harness types "gl <id> <verb> [args]" into the console (focus-free
// PostMessage to the game window, gamelab/winproc.py). Every reply is one
// "[GL] {...}" line in HWR2.exe.log carrying the same id, which the launcher
// tails. Verbs here never change game state, except the fixture verbs
// (char), which call the same functions the game's own windows call.
//
// A heartbeat line ("ev":"hb") goes out every second of gameplay frames with
// the current phase, so a hung or crashed run is detectable from the log.
//
// Module constructors run when the menu level loads, but nothing ticks until a
// gameplay session starts (docs/RE_NOTES.md, mod lifecycle). So the front door
// (main menu -> Singleplayer) is a key press, not a verb. Whether `gl` answers at
// the menu is not measured.
namespace GameLab
{
	const string VERSION = "0.1.0";

	funcdef void Verb(const string &in id, array<string>@ args);

	class Entry
	{
		string name;
		string help;
		Verb@ fn;
		Entry(const string &in n, const string &in h, Verb@ f) { name = n; help = h; @fn = f; }
	}

	array<Entry@> g_verbs;
	uint g_commands = 0;

	// other GameLab mods (gamelab-hands, gamelab-pilot) add verbs through this
	void RegisterVerb(const string &in name, const string &in help, Verb@ fn)
	{
		for (uint i = 0; i < g_verbs.length(); i++)
		{
			if (g_verbs[i].name == name)
			{
				@g_verbs[i] = Entry(name, help, fn);
				return;
			}
		}
		g_verbs.insertLast(Entry(name, help, fn));
	}

	Json@ Reply(const string &in id, bool ok)
	{
		Json j;
		j.Str("id", id).Bool("ok", ok);
		return j;
	}

	uint g_fails = 0;       // failed replies this process (setup counts its lines' failures)

	void Fail(const string &in id, const string &in error)
	{
		g_fails++;
		Emit(Reply(id, false).Str("error", error));
	}

	void ConsoleGl(cvar_t@ arg)
	{
		auto line = strTrim(arg.GetString());
		if (line.length() >= 2 && line.substr(0, 1) == "\"" && line.substr(line.length() - 1) == "\"")
			line = strTrim(line.substr(1, line.length() - 2));
		auto raw = line.split(" ");
		array<string> args;
		for (uint i = 0; i < raw.length(); i++)
		{
			if (raw[i].length() > 0)
				args.insertLast(raw[i]);
		}
		if (args.length() < 2)
		{
			Fail(args.length() > 0 ? args[0] : "", "usage: gl <id> <verb> [args]");
			return;
		}
		string id = args[0];
		string verb = args[1];
		args.removeRange(0, 2);
		if (RanRecently(id, verb))
			return;
		g_commands++;
		// a command typed while the next level preloads can reach a script module whose verb
		// registry isn't there yet (null access on g_verbs, probe-keys2 20261018-103121): the
		// command fails and the caller polls again
		try {
			RunVerb(id, verb, args);
		} catch {
			Fail(id, "probe not ready (level loading), try again");
		}
	}

	// multi <verb> [args] + <verb> [args] + ...: run each sub-command in this frame, the k-th
	// replying under id "<id>.<k>", then one reply under <id> with the count. One typed line
	// instead of one per probe: a fixture readback is 16 probes (session.gl_multi).
	void VerbMulti(const string &in id, array<string>@ args)
	{
		uint n = 0;
		array<string> cur;
		for (uint i = 0; i <= args.length(); i++)
		{
			if (i < args.length() && args[i] != "+")
			{
				cur.insertLast(args[i]);
				continue;
			}
			if (cur.length() == 0)
				continue;
			string verb = cur[0];
			cur.removeAt(0);
			if (verb == "multi")
				Fail(id + "." + n, "multi does not nest");
			else
				RunVerb(id + "." + n, verb, cur);
			n++;
			cur.resize(0);
		}
		Emit(Reply(id, true).Int("n", n));
	}

	// verbs run so far: a verb may change the scene mid-frame (spawn, teleport, ...), so the
	// Pilot's per-frame scene snapshot is keyed on this as well as the frame
	uint g_verbRuns = 0;

	void RunVerb(const string &in id, const string &in verb, array<string>@ args)
	{
		g_verbRuns++;
		for (uint i = 0; i < g_verbs.length(); i++)
		{
			if (g_verbs[i].name == verb)
			{
				// a probe must not be able to break the game: a throw becomes a failed reply
				// (the engine gives scripts no exception text, so the verb is all we can name)
				try {
					g_verbs[i].fn(id, args);
				} catch {
					g_exceptions++;
					Fail(id, "exception in verb '" + verb + "'");
				}
				return;
			}
		}
		Fail(id, "unknown verb '" + verb + "'");
	}

	uint g_exceptions = 0;
	uint g_boots = 0;        // GameLabProbeModule constructions this process (identity across levels)

	// ---- phase ----------------------------------------------------------------

	// "town" | "<mission id>/<level id>" | the level file outside a mission. The same answer as
	// gamelab-pilot's Place(), kept here so the probe does not depend on the pilot.
	// MissionManager::GetCurrentMission() dereferences g_module, null before a mission module
	// is built (Missions/MissionManager.as)
	string LevelPlace()
	{
		if (g_inTown)
			return "town";
		if (MissionManager::g_module is null)
			return GetCurrentLevelFilename();
		auto def = MissionManager::GetCurrentMission();
		if (def is null)
			return GetCurrentLevelFilename();
		uint i = MissionManager::g_module.m_missionLevelIndex;
		return def.m_id + "/" + (i < def.m_levels.length() ? def.m_levels[i].m_id : ("" + i));
	}

	// no_record | no_character | dead | town | mission
	string Phase()
	{
		auto record = GetLocalPlayerRecord();
		if (record is null)
			return "no_record";
		if (record.playerClass is null)
			return "no_character";
		if (record.IsDead())
			return "dead";
		return g_inTown ? "town" : "mission";
	}

	string TopWindow()
	{
		auto gm = cast<BaseGameMode>(g_gameMode);
		if (gm is null || gm.m_windowManager is null)
			return "";
		auto w = gm.m_windowManager.GetCurrentWindow();
		return w is null ? "" : Reflect::GetTypeName(w);
	}

	// ---- verbs ----------------------------------------------------------------

	// ping: liveness; the probe version, phase, boot count, level and commands served.
	void VerbPing(const string &in id, array<string>@ args)
	{
		Emit(Reply(id, true).Str("version", VERSION).Str("phase", Phase()).Int("boots", g_boots)
			.Str("level", GetCurrentLevelFilename()).Int("cmds", g_commands));
	}

	// help: every registered verb and its argument signature.
	void VerbHelp(const string &in id, array<string>@ args)
	{
		array<string> names;
		for (uint i = 0; i < g_verbs.length(); i++)
			names.insertLast(g_verbs[i].name + " " + g_verbs[i].help);
		Emit(Reply(id, true).Raw("verbs", StrArray(names)));
	}

	string PlayerJson()
	{
		auto record = GetLocalPlayerRecord();
		if (record is null)
			return "null";
		Json p;
		p.Str("name", record.name);
		p.Str("class", record.playerClass is null ? "" : record.playerClass.m_id);
		int level = record.level;
		int64 xp = record.experience;
		p.Int("level", level).Int("xp", xp);
		// Native earned and additional skill points; read-only fixture checks.
		p.Int("skillFree", record.GetFreeSkillPoints()).Int("bonusSkillPoints", record.bonusSkillPts);
		p.Int("hp", record.CurrentHealth()).Int("hpMax", record.MaxHealth());
		p.Int("mana", record.CurrentMana()).Int("manaMax", record.MaxMana());
		// dashes is the current charge count (saved as "dash-charges", recharging over time,
		// Player.as:1254); maxDashes is what the build grants
		p.Int("dashes", record.dashCharges).Int("maxDashes", record.currStats.MaxDashes);
		p.Int("portrait", record.portrait.length());
		p.Bool("dead", record.IsDead());
		auto plr = GetLocalPlayer();
		p.Bool("spawned", plr !is null);
		// Death removes the actor, but its record retains the same unrounded mana.
		if (plr is null && record.IsDead())
			p.Num("manaExact", record.mana * float(record.MaxMana()));
		if (plr !is null)
		{
			vec3 pos = plr.m_unit.GetPosition();
			p.Num("x", pos.x).Num("y", pos.y);
			p.Bool("combo", plr.m_comboActive);
			// mana as the float the costs come off (CurrentMana truncates), and the modifiers'
			// skill cost multiplier (chapel blessing, shrines, gear: Player.UsePoints)
			p.Num("manaExact", record.mana * float(record.MaxMana()));
			p.Num("manaCostMul", record.GetModifiers().SkillCostMul(plr).y);
			// active buffs by their name key (ActorBuffDef.m_name, e.g. ".hwp.groupcombo...")
			array<string> buffs;
			for (uint i = 0; i < plr.m_buffs.m_buffs.length(); i++)
			{
				auto b = plr.m_buffs.m_buffs[i];
				if (b !is null && b.m_def !is null)
					buffs.insertLast(b.m_def.m_name);
			}
			p.Raw("buffs", StrArray(buffs));
		}
		return p.Close();
	}

	// state: phase, level, NG+, open window and the local player (class, level, hp, position, combo, buffs); fixtures read back through it.
	void VerbState(const string &in id, array<string>@ args)
	{
		auto j = Reply(id, true);
		j.Str("phase", Phase());
		j.Str("level", GetCurrentLevelFilename());
		j.Bool("inTown", g_inTown);
		j.Num("ngp", g_ngp + 0.0f); // the NG+ enemies scale by (CompositeActorBehavior)
		j.Str("window", TopWindow());
		j.Raw("player", PlayerJson());
		Emit(j);
	}

	// which resource mods the running game sees and has enabled: the live half
	// of the environment check (gamelab/env/environments.json "mods")
	void VerbMods(const string &in id, array<string>@ args)
	{
		auto mods = Platform::GetAllResourceMods();
		array<string> items;
		for (uint i = 0; i < mods.length(); i++)
		{
			Json m;
			m.Str("id", mods[i].ID).Bool("enabled", PersistentSaves::IsModEnabled(mods[i])).Bool("packed", mods[i].Packaged);
			items.insertLast(m.Close());
		}
		Emit(Reply(id, true).Raw("mods", RawArray(items)));
	}

	// open windows, bottom to top, by script class
	void VerbUi(const string &in id, array<string>@ args)
	{
		auto gm = cast<BaseGameMode>(g_gameMode);
		array<string> names;
		if (gm !is null && gm.m_windowManager !is null)
		{
			for (uint i = 0; i < gm.m_windowManager.m_objects.length(); i++)
				names.insertLast(Reflect::GetTypeName(gm.m_windowManager.m_objects[i]));
		}
		Emit(Reply(id, true).Raw("windows", StrArray(names)));
	}

	// cvars <name>...: values as the running game holds them (the loaded settings,
	// not the file on disk); the launcher's mute check reads snd_volume* here
	void VerbCvars(const string &in id, array<string>@ args)
	{
		// read each by its own type: GetVarFloat on an int cvar returns 0 (v_fps_limit,
		// measured 2026-10-17); bools as 0/1
		Json vals;
		for (uint i = 0; i < args.length(); i++)
		{
			auto t = GetVarType(args[i]);
			if (t == cvar_type::Int)
				vals.Num(args[i], float(GetVarInt(args[i])));
			else if (t == cvar_type::Bool)
				vals.Num(args[i], GetVarBool(args[i]) ? 1.0f : 0.0f);
			else
				vals.Num(args[i], GetVarFloat(args[i]));
		}
		Emit(Reply(id, true).Raw("cvars", vals.Close()));
	}

	// inv: materials as the game reads them (PlayerRecord.GetMaterial: the town's store
	// while in town, the character's own on a mission)
	void VerbInv(const string &in id, array<string>@ args)
	{
		auto record = GetLocalPlayerRecord();
		if (record is null)
		{
			Fail(id, "no local player record");
			return;
		}
		array<string> names = { "gold", "wood", "stone", "iron", "crystals", "dust", "ore" };
		Json mats;
		for (uint i = 0; i < names.length(); i++)
			mats.Int(names[i], record.GetMaterial(MaterialType(i)));
		Emit(Reply(id, true).Str("store", cast<TownGameMode>(g_gameMode) !is null ? "town" : "character")
			.Raw("materials", mats.Close()));
	}

	string UnitJson(UnitPtr u, vec2 from)
	{
		Json e;
		vec3 pos = u.GetPosition();
		e.Int("unit", u.GetId()).Str("name", u.GetDebugName());
		ref@ b = u.GetScriptBehavior();
		e.Str("behavior", b is null ? "" : Reflect::GetTypeName(b));
		e.Bool("usable", cast<IUsable>(b) !is null);
		auto scene = u.GetCurrentUnitScene();
		e.Str("scene", scene is null ? "" : scene.GetName());
		auto mat = cast<Material::MaterialPickup>(b);
		if (mat !is null)
			e.Int("amount", mat.m_amount);
		auto actor = cast<Actor>(b);
		if (actor !is null)
			e.Num("hp", actor.GetHealth()).Int("hpMax", actor.GetMaxHp())
				.Num("hpExact", double(actor.GetHealth()) * double(actor.GetMaxHp())).Bool("dead", actor.IsDead());
		e.Num("x", pos.x).Num("y", pos.y).Num("dist", dist(from, xy(pos)));
		return e.Close();
	}

	const uint NEAR_CAP = 64;

	// near [radius] [filter]: units within radius (default 200) of the player,
	// nearest first, capped at NEAR_CAP; "truncated" reports how many were left out
	// Actor hp stays a fraction; hpMax and hpExact report native maximum and current HP units.
	// Each unit also reports its current scene (UnitPtr.GetCurrentUnitScene) and a material
	// pickup its amount (Material::MaterialPickup.m_amount, fixed when it was dropped).
	void VerbNear(const string &in id, array<string>@ args)
	{
		auto plr = GetLocalPlayer();
		if (plr is null)
		{
			Fail(id, "no spawned local player");
			return;
		}
		int radius = args.length() > 0 ? int(parseInt(args[0])) : 200;
		string filter = args.length() > 1 ? args[1] : "";
		vec2 center = xy(plr.m_unit.GetPosition());
		auto units = g_scene.FetchAllUnits(~0, center, radius);
		// only the nearest NEAR_CAP are kept in order: a sorted insert of all of them was O(n^2)
		// over ~14k units at radius 600 (doodads count) and held the frame ~1 s per call
		// (combat-escalate 20261019-065554, shim pace hitches)
		array<UnitPtr> keep;
		array<float> dists;
		uint count = 0;
		for (uint i = 0; i < units.length(); i++)
		{
			if (!units[i].IsValid() || units[i].IsDestroyed() || units[i] == plr.m_unit)
				continue;
			// FetchAllUnits' radius doesn't bound what it returns ("near 60" in town gave 764
			// units, plan-t8 075319), so the distance is checked here
			float d = dist(center, xy(units[i].GetPosition()));
			if (d > radius)
				continue;
			ref@ b = units[i].GetScriptBehavior();
			// the filter matches the behavior's type name or the unit's debug name (its .unit path)
			if (filter != "" && (b is null || Reflect::GetTypeName(b).findFirst(filter) < 0)
				&& units[i].GetDebugName().findFirst(filter) < 0)
				continue;
			count++;
			if (dists.length() >= NEAR_CAP && d >= dists[dists.length() - 1])
				continue;
			uint at = 0;
			while (at < dists.length() && dists[at] <= d)
				at++;
			keep.insertAt(at, units[i]);
			dists.insertAt(at, d);
			if (dists.length() > NEAR_CAP)
			{
				keep.removeLast();
				dists.removeLast();
			}
		}
		array<string> items;
		for (uint i = 0; i < keep.length(); i++)
			items.insertLast(UnitJson(keep[i], center));
		int truncated = count > NEAR_CAP ? int(count - NEAR_CAP) : 0;
		Emit(Reply(id, true).Int("radius", radius).Int("count", count).Int("truncated", truncated)
			.Raw("units", RawArray(items)));
	}

	const uint TRAPS_CAP = 96;

	void TrapList(Json@ r, const string &in name, array<string>@ list)
	{
		array<string> cut;
		for (uint i = 0; i < list.length() && i < TRAPS_CAP; i++)
			cut.insertLast(list[i]);
		r.Int(name + "Count", list.length())
			.Int(name + "Truncated", list.length() > TRAPS_CAP ? int(list.length() - TRAPS_CAP) : 0)
			.Raw(name, RawArray(cut));
	}

	// bossbars: read-only. The HUD's boss bar: whether its frame shows, the name it shows
	// (the boss-name text, after Resources::GetString) and each bar (its boss's unit, the
	// name it was added with, defeated), first TRAPS_CAP bars with the truncation.
	void VerbBossBars(const string &in id, array<string>@ args)
	{
		HUD@ hud = g_gameMode is null ? null : g_gameMode.GetHUD();
		if (hud is null)
		{
			Fail(id, "no HUD");
			return;
		}
		HUDBossBar@ bb = null;
		for (uint i = 0; i < hud.m_components.length() && bb is null; i++)
			@bb = cast<HUDBossBar>(hud.m_components[i]);
		if (bb is null)
		{
			Fail(id, "no boss bar component");
			return;
		}
		array<string> bars;
		for (uint i = 0; i < bb.m_barList.m_children.length(); i++)
		{
			auto w = cast<BossBarWidget>(bb.m_barList.m_children[i]);
			if (w is null || w.m_actor is null)
				continue;
			Json e;
			e.Str("unit", w.m_actor.m_unit.IsValid() ? w.m_actor.m_unit.GetDebugName() : "")
				.Str("name", w.m_name).Bool("defeated", w.IsDefeated());
			bars.insertLast(e.Close());
		}
		Json@ r = Reply(id, true);
		r.Bool("shown", bb.m_mainFrame.m_visible).Str("title", bb.m_bossName is null ? "" : bb.m_bossName.m_str);
		TrapList(r, "bars", bars);
		Emit(r);
	}

	// bubbles: read-only. The speech bubbles open now (BaseGameMode's user windows that are a
	// SpeechBubbleContainer and visible): the text shown, the unit it hangs over, how long it
	// has shown and its time (ms), first TRAPS_CAP with the truncation.
	void VerbBubbles(const string &in id, array<string>@ args)
	{
		auto gm = cast<BaseGameMode>(g_gameMode);
		if (gm is null)
		{
			Fail(id, "no BaseGameMode");
			return;
		}
		array<string> open;
		for (uint i = 0; i < gm.m_userWindows.length(); i++)
		{
			auto c = cast<SpeechBubbleContainer>(gm.m_userWindows[i]);
			if (c is null || !c.m_visible || c.m_speechBubble is null)
				continue;
			Json e;
			e.Str("text", c.m_speechBubble.m_text).Str("unit", c.m_unit.IsValid() ? c.m_unit.GetDebugName() : "")
				.Int("shown", c.m_timerC).Int("timer", c.m_speechBubble.m_timer);
			open.insertLast(e.Close());
		}
		Json@ r = Reply(id, true);
		TrapList(r, "bubbles", open);
		Emit(r);
	}

	// traps [radius]: read-only. The hazards within radius (default 800) of the player, by kind,
	// nearest first, each list capped at TRAPS_CAP with its truncation. "shooters": every
	// WorldScript::ProjectileShooter (position, Direction in degrees, Spread, enabled; the trigger
	// that fires it is native and not readable). "areas": units whose behavior is a
	// DangerAreaBehavior (sawblades, floor_fire/curse/spikes, ProximityTrap): debug name, freq,
	// current scene names ("on"/"off" for toggled ones). "actors": trap-team actors (statues).
	// "rays": live projectiles with no owner (trap fire balls, the HoH1 tower's trap shots), with their direction.
	void VerbTraps(const string &in id, array<string>@ args)
	{
		auto plr = GetLocalPlayer();
		if (plr is null)
		{
			Fail(id, "no spawned local player");
			return;
		}
		float radius = args.length() > 0 ? parseFloat(args[0]) : 800;
		vec2 center = xy(plr.m_unit.GetPosition());

		array<string> shooters;
		array<float> sd;
		auto ws = g_scene.FetchAllWorldScripts("ProjectileShooter");
		for (uint i = 0; i < ws.length(); i++)
		{
			auto u = ws[i].GetUnit();
			float d = dist(center, xy(u.GetPosition()));
			if (d > radius)
				continue;
			auto sh = cast<WorldScript::ProjectileShooter>(u.GetScriptBehavior());
			Json e;
			e.Int("unit", u.GetId()).Num("x", u.GetPosition().x).Num("y", u.GetPosition().y).Num("dist", d)
				.Int("dir", sh is null ? -1 : sh.Direction).Int("spread", sh is null ? 0 : sh.Spread)
				.Bool("enabled", ws[i].IsEnabled());
			uint at = 0;
			while (at < sd.length() && sd[at] <= d)
				at++;
			shooters.insertAt(at, e.Close());
			sd.insertAt(at, d);
		}

		array<string> areas, actors, rays;
		array<float> ad, td, rd;
		auto units = g_scene.FetchAllUnits(~0, center, int(radius));
		for (uint i = 0; i < units.length(); i++)
		{
			if (!units[i].IsValid() || units[i].IsDestroyed())
				continue;
			ref@ b = units[i].GetScriptBehavior();
			if (b is null)
				continue;
			auto da = cast<DangerAreaBehavior>(b);
			auto ac = cast<Actor>(b);
			// any projectile with no owner is a trap's shot: RayProjectiles and the HoH1 tower's
			// own kinds (campaign's HoH1Projectile is a ProjectileBase)
			auto rp = cast<IProjectile>(b);
			// classified before the entry is built: building one per unit (~14k with a behavior on
			// a floor) cost more than the traps themselves
			if (da is null && (ac is null || ac.Team != g_team_trap) && (rp is null || rp.GetOwner() !is null))
				continue;
			vec2 p = xy(units[i].GetPosition());
			float d = dist(center, p);
			Json e;
			e.Int("unit", units[i].GetId()).Str("name", units[i].GetDebugName()).Num("x", p.x).Num("y", p.y).Num("dist", d);
			array<string>@ list = null;
			array<float>@ ds = null;
			if (da !is null)
			{
				auto sc = units[i].GetAllCurrentUnitSceneNames();
				string scs = "";
				for (uint k = 0; sc !is null && k < sc.length(); k++)
					scs += (k > 0 ? "," : "") + sc[k];
				e.Str("behavior", Reflect::GetTypeName(b)).Int("freq", da.m_freq).Str("scenes", scs);
				@list = areas;
				@ds = ad;
			}
			else if (ac !is null && ac.Team == g_team_trap)
			{
				e.Str("behavior", Reflect::GetTypeName(b));
				@list = actors;
				@ds = td;
			}
			else if (rp !is null && rp.GetOwner() is null)
			{
				vec2 dir = rp.GetDirection();
				e.Num("dx", dir.x).Num("dy", dir.y);
				@list = rays;
				@ds = rd;
			}
			if (list is null)
				continue;
			uint at = 0;
			while (at < ds.length() && ds[at] <= d)
				at++;
			list.insertAt(at, e.Close());
			ds.insertAt(at, d);
		}
		Json@ r = Reply(id, true);
		r.Num("radius", radius).Num("x", center.x).Num("y", center.y);
		TrapList(r, "shooters", shooters);
		TrapList(r, "areas", areas);
		TrapList(r, "actors", actors);
		TrapList(r, "rays", rays);
		Emit(r);
	}

	// areatriggers [radius]: read-only. The level's area triggers (WorldScript::AreaTrigger and
	// AllPlayersAreaTrigger, WorldScript/Triggers/) within radius (default 12000) of the player,
	// nearest first, capped at AREA_TRIGGER_CAP with truncation reported: the script unit's position,
	// enabled, the number of areas and how many units each holds right now. A CollisionArea's
	// shape is native and not readable, so the position is the script's, which an editor places
	// by its area. A boss level spawns its boss from one of these (SpawnUnit on enter), so a bot
	// walks into them to start the fight. The script can sit far from its area (boss_arista.lvl:
	// AreaTrigger 1449 at -384,448, its area unit 16 a 480x128 sensor at 0,240; maps-floors-low
	// 20261020-162214 had no route to the script's spot), so ax/ay is the mean position of the
	// units inside the areas, the best estimate of where the area is (absent when none are).
	const uint AREA_TRIGGER_CAP = 20; // ~160 bytes each, under the ~4 KB reply budget

	void VerbAreaTriggers(const string &in id, array<string>@ args)
	{
		auto plr = GetLocalPlayer();
		if (plr is null)
		{
			Fail(id, "no spawned local player");
			return;
		}
		float radius = args.length() > 0 ? parseFloat(args[0]) : 12000;
		vec2 center = xy(plr.m_unit.GetPosition());
		array<string> list;
		array<float> ds;
		array<string> types = { "AreaTrigger", "AllPlayersAreaTrigger" };
		for (uint t = 0; t < types.length(); t++)
		{
			auto ws = g_scene.FetchAllWorldScripts(types[t]);
			for (uint i = 0; i < ws.length(); i++)
			{
				auto u = ws[i].GetUnit();
				float d = dist(center, xy(u.GetPosition()));
				if (d > radius)
					continue;
				int nAreas = 0, inside = 0;
				vec2 sum;
				auto at = cast<WorldScript::AreaTrigger>(u.GetScriptBehavior());
				auto ap = cast<WorldScript::AllPlayersAreaTrigger>(u.GetScriptBehavior());
				array<CollisionArea@>@ areas = at !is null ? at.Areas : (ap !is null ? ap.Areas : null);
				if (areas !is null)
				{
					nAreas = int(areas.length());
					for (uint a = 0; a < areas.length(); a++)
						if (areas[a] !is null)
						{
							auto got = areas[a].FetchAllInside(g_scene);
							for (uint j = 0; j < got.length(); j++)
								sum += xy(got[j].GetPosition());
							inside += int(got.length());
						}
				}
				Json e;
				e.Str("type", types[t]).Int("unit", u.GetId()).Num("x", u.GetPosition().x).Num("y", u.GetPosition().y)
					.Num("dist", d).Bool("enabled", ws[i].IsEnabled()).Int("areas", nAreas).Int("inside", inside);
				if (inside > 0)
					e.Int("ax", int(sum.x / inside)).Int("ay", int(sum.y / inside));
				uint k = 0;
				while (k < ds.length() && ds[k] <= d)
					k++;
				list.insertAt(k, e.Close());
				ds.insertAt(k, d);
			}
		}
		Json@ r = Reply(id, true);
		r.Num("radius", radius).Num("x", center.x).Num("y", center.y);
		array<string> cut;
		for (uint i = 0; i < list.length() && i < AREA_TRIGGER_CAP; i++)
			cut.insertLast(list[i]);
		r.Int("count", list.length())
			.Int("truncated", list.length() > AREA_TRIGGER_CAP ? int(list.length() - AREA_TRIGGER_CAP) : 0)
			.Raw("triggers", RawArray(cut));
		Emit(r);
	}

	// run: the current run's build state, as the record holds it right now (the save writes
	// the same fields: PlayerRecord.as:600-880). Trinkets (trinketInventory, attuned or not),
	// temporary skill levels from spheres and the like (pickedTempSkills), equipped gear and the
	// gear inventory, run buffs (missionBuffs: tavern food and drinks, boons, the travelling
	// cook; architectBuffs), elixirs, carried materials, keys, potion charges, rerolls, shadow
	// curses. Lists are capped at RUN_CAP each, with truncation reported.
	const uint RUN_CAP = 40;

	void VerbRun(const string &in id, array<string>@ args)
	{
		auto rec = GetLocalPlayerRecord();
		if (rec is null || rec.playerClass is null)
		{
			Fail(id, "no local character");
			return;
		}
		bool truncated = false;

		array<string> trinkets;
		for (uint i = 0; i < rec.trinketInventory.m_items.length(); i++)
		{
			if (trinkets.length() >= RUN_CAP) { truncated = true; break; }
			auto t = rec.trinketInventory.m_items[i];
			if (t is null)
				continue;
			Json e;
			e.Str("id", t.m_id).Str("name", Resources::GetString(t.m_name)).Int("quality", int(t.m_quality))
				.Bool("attuned", rec.attunedTrinkets.findByRef(t) >= 0);
			trinkets.insertLast(e.Close());
		}

		Json temp;
		auto keys = rec.pickedTempSkills.getKeys();
		for (uint i = 0; i < keys.length() && i < RUN_CAP; i++)
		{
			int lvl = 0;
			rec.pickedTempSkills.get(keys[i], lvl);
			temp.Int(keys[i], lvl);
		}
		truncated = truncated || keys.length() > RUN_CAP;

		array<string> equipped;
		for (uint i = 0; i < rec.equipped.m_items.length(); i++)
		{
			auto it = rec.equipped.m_items[i];
			if (it is null)
				continue;
			auto gi = cast<Equipment::Item>(it);
			Json e;
			e.Int("slot", i).Str("id", gi !is null && gi.baseItem !is null ? gi.baseItem.m_id : "")
				.Str("name", it.GetName()).Int("quality", int(it.GetQuality())).Int("ilvl", it.GetItemLevel());
			equipped.insertLast(e.Close());
		}

		array<string> bag;
		for (uint i = 0; i < rec.equipInventory.m_items.length(); i++)
		{
			if (bag.length() >= RUN_CAP) { truncated = true; break; }
			auto it = rec.equipInventory.m_items[i];
			if (it is null)
				continue;
			auto gi = cast<Equipment::Item>(it);
			Json e;
			e.Str("id", gi !is null && gi.baseItem !is null ? gi.baseItem.m_id : "")
				.Str("name", it.GetName()).Int("quality", int(it.GetQuality())).Int("ilvl", it.GetItemLevel());
			bag.insertLast(e.Close());
		}

		array<string> buffs;
		for (uint i = 0; i < rec.missionBuffs.length() && buffs.length() < RUN_CAP; i++)
		{
			auto b = rec.missionBuffs[i].m_buff;
			if (b is null)
				continue;
			Json e;
			e.Str("id", b.m_id).Str("name", b.m_name).Int("quality", int(b.m_quality)).Int("slot", int(rec.missionBuffs[i].m_id));
			buffs.insertLast(e.Close());
		}
		array<string> arch;
		for (uint i = 0; i < rec.architectBuffs.length() && arch.length() < RUN_CAP; i++)
		{
			auto b = rec.architectBuffs[i];
			if (b is null)
				continue;
			Json e;
			e.Str("id", b.m_id).Str("name", b.m_name).Int("quality", int(b.m_quality));
			arch.insertLast(e.Close());
		}

		array<string> mats;
		for (uint i = 0; i < rec.materials.length(); i++)
			mats.insertLast("" + int(rec.materials[i]));
		Json keysJ;
		auto kk = rec.keys.getKeys();
		for (uint i = 0; i < kk.length() && i < RUN_CAP; i++)
		{
			int n = 0;
			rec.keys.get(kk[i], n);
			keysJ.Int(kk[i], n);
		}

		Json elix;
		elix.Int("str", rec.elixirStr).Int("dex", rec.elixirDex).Int("int", rec.elixirInt).Int("foc", rec.elixirFoc).Int("vit", rec.elixirVit);

		Emit(Reply(id, true).Str("class", rec.playerClass.m_id).Int("level", rec.level)
			.Raw("trinkets", RawArray(trinkets)).Raw("tempSkills", temp.Close())
			.Raw("equipped", RawArray(equipped)).Raw("bag", RawArray(bag)).Int("valuables", rec.valuableInventory.m_valuables.length())
			.Raw("missionBuffs", RawArray(buffs)).Raw("architectBuffs", RawArray(arch))
			.Raw("elixirs", elix.Close()).Raw("materials", "[" + join(mats, ",") + "]").Raw("keys", keysJ.Close())
			.Int("potionCharges", rec.currStats.PotionCharges).Int("potionChargesUsed", rec.potionChargesUsed)
			.Int("rerollsUsed", rec.rerollsUsed).Int("shadowCurses", rec.shadowCurses)
			.Bool("truncated", truncated));
	}

	// usables: what the player could interact with right now, top (the one Use acts on) first
	void VerbUsables(const string &in id, array<string>@ args)
	{
		auto plr = GetLocalPlayer();
		if (plr is null)
		{
			Fail(id, "no spawned local player");
			return;
		}
		vec2 center = xy(plr.m_unit.GetPosition());
		auto top = plr.GetTopUsable();
		array<string> items;
		for (uint i = 0; i < plr.m_usables.length(); i++)
		{
			auto usable = plr.m_usables[i].m_usable;
			Json u;
			u.Raw("unit", UnitJson(usable.GetUseUnit(), center)).Bool("canUse", usable.CanUse(plr)).Bool("top", usable is top);
			items.insertLast(u.Close());
		}
		Emit(Reply(id, true).Raw("usables", RawArray(items)));
	}

	// overlays: everything drawn over the world at this moment, so a scenario can require
	// the set to be empty or expected (repro playbook 1.3). Windows (bottom to top), the
	// tutorial panel (Tutorials::TutorialModule.m_showing, drawn by HUDTutorials), live
	// announce / loot-log entries (HUDAnnounce subclasses, style id + text) and the
	// boss bar. HUD notifications are not listed: HoH2's AddNotification is a stub
	// ("TODO: Add notifications", WorldScript/GUI/AddNotification.as).
	void VerbOverlays(const string &in id, array<string>@ args)
	{
		auto j = Reply(id, true);
		auto gm = cast<BaseGameMode>(g_gameMode);
		array<string> windows;
		if (gm !is null && gm.m_windowManager !is null)
		{
			for (uint i = 0; i < gm.m_windowManager.m_objects.length(); i++)
				windows.insertLast(Reflect::GetTypeName(gm.m_windowManager.m_objects[i]));
		}
		j.Raw("windows", StrArray(windows));
		string tutorial = "";
		auto agm = cast<AGameplayGameMode>(g_gameMode);
		if (agm !is null)
		{
			for (uint i = 0; i < agm.m_modules.length(); i++)
			{
				auto tutMod = cast<Tutorials::TutorialModule>(agm.m_modules[i]);
				if (tutMod !is null && tutMod.m_showing !is null)
					tutorial = tutMod.m_showing.m_id;
			}
		}
		j.Str("tutorial", tutorial);
		array<string> announces;
		bool bossBar = false;
		auto hud = GetHUD();
		if (hud !is null)
		{
			for (uint i = 0; i < hud.m_components.length(); i++)
			{
				auto comp = hud.m_components[i];
				auto ann = cast<HUDAnnounce>(comp);
				if (ann !is null && comp.m_visible)
				{
					for (uint k = 0; k < ann.m_announceObjects.length(); k++)
					{
						auto obj = ann.m_announceObjects[k];
						if (obj is null)
							continue;
						Json a;
						a.Str("hud", Reflect::GetTypeName(comp)).Str("style", obj.m_style is null ? "" : obj.m_style.m_id);
						auto txt = cast<HUDAnnounceText>(obj);
						a.Str("text", txt is null ? "" : txt.m_textStr);
						announces.insertLast(a.Close());
					}
				}
				auto boss = cast<HUDBossBar>(comp);
				if (boss !is null && comp.m_visible && boss.m_barList !is null && boss.m_barList.m_children.length() > 0)
					bossBar = true;
			}
		}
		j.Raw("announces", RawArray(announces));
		j.Bool("bossBar", bossBar);
		Emit(j);
	}

	// buildings: the current town record's buildings (id -> variation), as the town
	// builder and the gambler read them (TownRecord.GetVariationOnBuilding)
	void VerbBuildings(const string &in id, array<string>@ args)
	{
		if (g_currTownRecord is null)
		{
			Fail(id, "no town record");
			return;
		}
		Json b;
		for (uint i = 0; i < g_currTownRecord.m_buildings.length(); i++)
		{
			auto def = g_currTownRecord.m_buildings[i].buildingDef;
			if (def !is null)
				b.Int(def.m_id, g_currTownRecord.m_buildings[i].variation);
		}
		Emit(Reply(id, true).Int("count", g_currTownRecord.m_buildings.length()).Raw("buildings", b.Close()));
	}

	const int FETCHBENCH_REPS = 1000;

	// fetchbench <radius> [reps] [all|foes|units]: measurement. g_scene.FetchAllUnits(~0, ...) (or
	// FetchActorsWithOtherTeam(player team, ...), or FetchUnits(~0, ...)) around the player, `reps` times in one frame;
	// scripts have no wall clock, so time it from outside: the reply's latency minus reps=0's.
	// Also what one call returns: how many, how many lie within the radius, the farthest
	void VerbFetchBench(const string &in id, array<string>@ args)
	{
		auto plr = GetLocalPlayer();
		if (plr is null)
		{
			Fail(id, "no spawned local player");
			return;
		}
		int radius = args.length() > 0 ? int(parseInt(args[0])) : 100;
		int reps = args.length() > 1 ? int(parseInt(args[1])) : 0;
		string kind = args.length() > 2 ? args[2] : "all";
		if (kind != "all" && kind != "foes" && kind != "units")
		{
			Fail(id, "kind is all|foes|units");
			return;
		}
		bool capped = reps > FETCHBENCH_REPS;
		if (capped)
			reps = FETCHBENCH_REPS;
		vec2 center = xy(plr.m_unit.GetPosition());
		uint total = 0;
		for (int k = 0; k < reps; k++)
			total += FetchBenchOnce(kind, center, radius).length();
		auto one = FetchBenchOnce(kind, center, radius);
		int inside = 0;
		float far = 0;
		dictionary got;
		for (uint i = 0; i < one.length(); i++)
		{
			float d = dist(center, xy(one[i].GetPosition()));
			if (d <= radius)
				inside++;
			far = max(far, d);
			got.set("" + one[i].GetId(), true);
		}
		// missing: units FetchAllUnits returns with their centre inside the radius that this
		// kind's result lacks (0 for kind all); what a caller filtering on centre distance loses
		int missing = 0;
		if (kind == "units")
		{
			auto all = g_scene.FetchAllUnits(~0, center, radius);
			for (uint i = 0; i < all.length(); i++)
				if (dist(center, xy(all[i].GetPosition())) <= radius && !got.exists("" + all[i].GetId()))
					missing++;
		}
		// farCount: the same fetch centred 100000 px off the level, radius 1 (the whole scene
		// again when FetchAllUnits ignores its centre too)
		int farCount = int(FetchBenchOnce(kind, center + vec2(100000, 100000), 1).length());
		Emit(Reply(id, true).Int("radius", radius).Int("reps", reps).Bool("repsCapped", capped)
			.Str("kind", kind).Int("count", one.length()).Int("inside", inside)
			.Num("farthest", far).Int("missing", missing).Int("farCount", farCount).Int("total", total));
	}

	array<UnitPtr>@ FetchBenchOnce(const string &in kind, vec2 center, int radius)
	{
		if (kind == "foes")
			return g_scene.FetchActorsWithOtherTeam(g_team_player, center, radius);
		if (kind == "units")
			return g_scene.FetchUnits(~0, center, radius);
		return g_scene.FetchAllUnits(~0, center, radius);
	}

	// clock: scene time (g_scene.GetTime(), what behaviours time themselves with), the
	// probe's own frame count, and the time-scale / hour cvars
	uint g_frames = 0;
	void VerbClock(const string &in id, array<string>@ args)
	{
		Emit(Reply(id, true).Int("sceneMs", g_scene is null ? -1 : int(g_scene.GetTime())).Int("frames", g_frames)
			.Num("timescale", GetVarFloat("g_timescale")).Int("hour", GetVarInt("g_time_hour")));
	}

	const uint WIDGET_CAP = 400;
	// the game's log cuts a line at ~16400 characters, and printing one that long
	// crashed the game (deathrecap-death 20261020-112418, the DeadMenu plus every HUD
	// tree at depth 14), so the nodes stop at this many bytes
	const uint WIDGET_BYTES = 11000;

	// widgets [depth] [root] [type]: the UI widget tree of every open window (top last) and the
	// HUD, depth-first, capped at WIDGET_CAP nodes, WIDGET_BYTES of nodes and `depth` levels
	// (default 6); reports truncation. `root` keeps only the root of that name
	// ("DeadMenu", "HUD", "HUD:HWPDeathRecapHUD"); a window's root keeps its open tab too. A
	// tabbed window's open tab is a root of its own, "<window>:<tab class>"
	// ("PlayerMenu:PlayerMenuCharacterTab"). Per node: depth, script class, id, visible, size,
	// text (TextWidget), enabled (buttons), item (item slots), and where it is on screen
	// (WidgetPos, ProbeUi.as): x/y in GUI units, px/py its centre in window pixels, the
	// coordinates a `click`/`hover` step posts.
	int g_widgetCut = 0;    // nodes left out by the current widgets call
	string g_widgetType;    // the current call's type filter, "" for every node
	uint g_widgetBytes = 0; // node bytes the current widgets call holds

	void WidgetNodes(Widget@ w, int depth, int maxDepth, array<string>@ acc, vec2 origin = vec2(), float hostScale = 1.0f)
	{
		if (w is null)
			return;
		if (acc.length() >= WIDGET_CAP || g_widgetBytes >= WIDGET_BYTES)
		{
			g_widgetCut++;
			return;
		}
		string type = Reflect::GetTypeName(w);
		// a type filter skips the node but walks its children: the byte cap spent on the
		// menu's frames left out every bag item (droptrade-drop 20261020-145826, 7 of 11)
		bool keep = g_widgetType == "" || type == g_widgetType;
		if (keep)
		{
			Json n;
			n.Int("d", depth).Str("type", type).Str("id", w.m_id).Bool("visible", w.m_visible)
				.Int("w", w.m_width).Int("h", w.m_height);
			WidgetPos(n, w, origin, hostScale);
			auto t = cast<TextWidget>(w);
			if (t !is null)
				n.Str("text", t.m_str);
			auto iw = cast<AInteractableWidget>(w);
			if (iw !is null)
				n.Bool("enabled", iw.m_enabled);
			auto slot = cast<ItemWidgetBase>(w);
			if (slot !is null && slot.m_item !is null)
				n.Str("item", slot.m_item.GetName());
			string node = n.Close();
			g_widgetBytes += node.length();
			acc.insertLast(node);
		}
		if (w.m_children is null)
			return;
		if (depth >= maxDepth)
		{
			g_widgetCut += w.m_children.length();
			return;
		}
		for (uint i = 0; i < w.m_children.length(); i++)
			WidgetNodes(w.m_children[i], depth + 1, maxDepth, acc, origin, hostScale);
	}

	// A tabbed window's open tab is its own AWindowObject (GUI/MenuTabSystem.as), whose
	// widget tree isn't under the window's: the character screen's gear slots live there.
	MenuTabSystem@ TabsOf(IWidgetHoster@ w)
	{
		auto pm = cast<PlayerMenu>(w);
		if (pm !is null)
			return pm.m_tabSystem;
		auto gh = cast<GuildHall>(w);
		if (gh !is null)
			return gh.m_tabSystem;
		auto om = cast<WindowOptionsMenu>(w);
		if (om !is null)
			return om.m_tabSystem;
		auto cc = cast<CreateCharacterWindow>(w);
		if (cc !is null)
			return cc.m_tabSystem;
		auto mt = cast<MenuTab>(w);
		if (mt !is null)
			return mt.m_tabSystem;
		return null;
	}

	// a MenuTab's own m_tabSystem is the one it sits in, unless it has tabs of its own:
	// only a different system is a nested row. Kept when `only` is empty, the window's own
	// root (`keepAll`) or this tab's name; positioned from the tab's m_origin
	void TabRoots(IWidgetHoster@ w, const string &in name, int maxDepth, array<string>@ roots, MenuTabSystem@ parent,
		const string &in only, bool keepAll)
	{
		auto tabs = TabsOf(w);
		if (tabs is null || tabs is parent || tabs.m_currentIndex < 0 || tabs.m_currentIndex >= int(tabs.m_tabs.length()))
			return;
		auto tab = tabs.m_tabs[tabs.m_currentIndex];
		if (tab is null)
			return;
		string tname = name + ":" + Reflect::GetTypeName(tab);
		bool keep = keepAll || only == "" || only == tname;
		if (keep)
		{
			array<string> nodes;
			WidgetNodes(tab.m_widget, 0, maxDepth, nodes, tab.m_origin);
			Json r;
			r.Str("root", tname).Raw("nodes", RawArray(nodes));
			roots.insertLast(r.Close());
		}
		TabRoots(tab, tname, maxDepth, roots, tabs, only, keep && only != "");
	}

	// widgets [depth] [root] [type]: the UI widget tree of every open window (and its open tab) and the HUD (or only the root named `root`; a window keeps its tabs too; with `type`, only nodes of that script class, children still walked), capped, with truncation reported. Each node has its screen position (x/y GUI units, px/py centre in window pixels) and the reply a "screen" block (GUI scale and size, where the game sees the mouse).
	void VerbWidgets(const string &in id, array<string>@ args)
	{
		int maxDepth = args.length() > 0 ? int(parseInt(args[0])) : 6;
		string only = args.length() > 1 ? args[1] : "";
		g_widgetType = args.length() > 2 ? args[2] : "";
		array<string> roots;
		g_widgetCut = 0;
		g_widgetBytes = 0;
		auto gm = cast<BaseGameMode>(g_gameMode);
		if (gm !is null && gm.m_windowManager !is null)
		{
			for (uint i = 0; i < gm.m_windowManager.m_objects.length(); i++)
			{
				string name = Reflect::GetTypeName(gm.m_windowManager.m_objects[i]);
				auto win = cast<IWidgetHoster>(gm.m_windowManager.m_objects[i]);
				if (only == "" || name == only)
				{
					array<string> nodes;
					if (win !is null)
						WidgetNodes(win.m_widget, 0, maxDepth, nodes, win.m_origin);
					Json r;
					r.Str("root", name).Raw("nodes", RawArray(nodes));
					roots.insertLast(r.Close());
				}
				if (win !is null)
					TabRoots(win, name, maxDepth, roots, null, only, only != "" && name == only);
			}
		}
		auto hud = GetHUD();
		if (hud !is null)
		{
			if (only == "" || only == "HUD")
			{
				array<string> nodes;
				WidgetNodes(hud.m_widget, 0, maxDepth, nodes, hud.m_origin);
				Json r;
				r.Str("root", "HUD").Raw("nodes", RawArray(nodes));
				roots.insertLast(r.Close());
			}
			// each HUD component hosts its own tree (HUD.m_components, GUI/HUD/HUD.as)
			for (uint i = 0; i < hud.m_components.length(); i++)
			{
				string cname = "HUD:" + Reflect::GetTypeName(hud.m_components[i]);
				if (only != "" && cname != only)
					continue;
				array<string> cnodes;
				// drawn at (origin + m_offset) * m_scale (HUDComponent::Draw's transform)
				WidgetNodes(hud.m_components[i].m_widget, 0, maxDepth, cnodes, hud.m_components[i].m_offset, hud.m_components[i].m_scale);
				Json cr;
				cr.Str("root", cname).Bool("visible", hud.m_components[i].m_visible)
					.Raw("nodes", RawArray(cnodes));
				roots.insertLast(cr.Close());
			}
		}
		Emit(Reply(id, true).Int("depth", maxDepth).Int("truncated", g_widgetCut).Raw("screen", ScreenJson()).Raw("roots", RawArray(roots)));
	}

	const int TERRAIN_CELLS = 48;

	// terrain [radius] [step]: occupancy grid around the player from the game's own point
	// query (g_scene.QueryRect(pos, 1, 1, ~0, RaycastType::Any), the test SpawnPrefab uses
	// for "can something stand here"). Rows north to south: '.' free, '#' blocked,
	// '@' the player. At most TERRAIN_CELLS x TERRAIN_CELLS; "truncated" when clipped.
	void VerbTerrain(const string &in id, array<string>@ args)
	{
		auto plr = GetLocalPlayer();
		if (plr is null)
		{
			Fail(id, "no spawned local player");
			return;
		}
		int radius = args.length() > 0 ? int(parseInt(args[0])) : 160;
		int step = args.length() > 1 ? max(4, int(parseInt(args[1]))) : 16;
		int n = radius * 2 / step + 1;
		bool truncated = n > TERRAIN_CELLS;
		if (truncated)
			n = TERRAIN_CELLS;
		vec2 c = xy(plr.m_unit.GetPosition());
		array<string> rows;
		int blocked = 0;
		for (int y = 0; y < n; y++)
		{
			string row = "";
			for (int x = 0; x < n; x++)
			{
				vec2 p = c + vec2(float((x - n / 2) * step), float((y - n / 2) * step));
				if (x == n / 2 && y == n / 2)
				{
					row += "@";
					continue;
				}
				auto hits = g_scene.QueryRect(p, 1, 1, ~0, RaycastType::Any);
				bool solid = false;
				for (uint i = 0; i < hits.length() && !solid; i++)
					solid = hits[i] != plr.m_unit;
				if (solid)
					blocked++;
				row += solid ? "#" : ".";
			}
			rows.insertLast(row);
		}
		Emit(Reply(id, true).Num("x", c.x).Num("y", c.y).Int("step", step).Int("size", n).Int("blocked", blocked)
			.Bool("truncated", truncated).Raw("rows", StrArray(rows)));
	}

	const uint MEMBERS_CAP = 200;

	// members <TypeName>: the script type's properties (name + type) through the engine's
	// reflection (Reflect::GetType / TypeInfo.GetProperties). Read-only by construction:
	// it never touches an instance. Capped at MEMBERS_CAP; reports truncation.
	void VerbMembers(const string &in id, array<string>@ args)
	{
		if (args.length() < 1)
		{
			Fail(id, "usage: members <TypeName>");
			return;
		}
		auto t = Reflect::GetType(args[0]);
		if (t is null)
		{
			Fail(id, "no script type '" + args[0] + "'");
			return;
		}
		auto props = t.GetProperties();
		array<string> items;
		for (uint i = 0; i < props.length() && i < MEMBERS_CAP; i++)
		{
			Json p;
			auto pt = props[i].GetType();
			p.Str("name", props[i].GetName()).Str("type", pt is null ? "primitive" : pt.GetName());
			items.insertLast(p.Close());
		}
		auto base = t.GetBaseType();
		Emit(Reply(id, true).Str("type", t.GetName()).Str("base", base is null ? "" : base.GetName())
			.Int("count", props.length()).Int("truncated", props.length() > MEMBERS_CAP ? int(props.length() - MEMBERS_CAP) : 0)
			.Raw("members", RawArray(items)));
	}

	// inspect <root> [dotted.path]: a live record as the game itself serializes it.
	// Reflection has no value getter (members lists names only), so the value side goes
	// through the record's own Save(SValueBuilder), the same call SavePlayerAndTown makes:
	//   player -> GetLocalPlayerRecord().Save   (only reads fields and prints a log line)
	//   town   -> g_currTownRecord.Save         (also runs the TownRecordSave hook)
	// Nothing is written: the built SValue is never handed to PersistentSaves.
	// Path segments are dictionary keys or array indices ("inventory.0.id"). Output is
	// capped at INSPECT_CAP characters; past that only the keys / length come back.
	const uint INSPECT_CAP = 4000;

	SValue@ InspectRoot(const string &in root, string &out err)
	{
		SValueBuilder builder;
		if (root == "player")
		{
			auto plr = GetLocalPlayerRecord();
			if (plr is null)
			{
				err = "no local player record";
				return null;
			}
			builder.PushDictionary();
			plr.Save(builder);
			builder.PopDictionary();
			return builder.Build();
		}
		if (root == "town")
		{
			if (g_currTownRecord is null)
			{
				err = "no town record";
				return null;
			}
			if (!g_currTownRecord.Save(builder))
			{
				err = "town record is empty (Save returned false)";
				return null;
			}
			return builder.Build();
		}
		err = "unknown root '" + root + "' (player, town)";
		return null;
	}

	// inspect <player|town> [dotted.path]: read-only. A field of the player or town save record by dotted path, JSON-encoded, capped.
	void VerbInspect(const string &in id, array<string>@ args)
	{
		if (args.length() < 1)
		{
			Fail(id, "usage: inspect <player|town> [dotted.path]");
			return;
		}
		string err;
		SValue@ sv = InspectRoot(args[0], err);
		if (sv is null)
		{
			Fail(id, err);
			return;
		}
		string path = args.length() > 1 ? args[1] : "";
		array<string>@ segs = path.length() > 0 ? path.split(".") : array<string>();
		for (uint i = 0; i < segs.length(); i++)
		{
			auto t = sv.GetType();
			SValue@ next = null;
			if (t == SValueType::Dictionary)
				@next = sv.GetDictionaryEntry(segs[i]);
			else if (t == SValueType::Array)
			{
				int k = parseInt(segs[i]);
				auto arr = sv.GetArray();
				if (k >= 0 && uint(k) < arr.length())
					@next = arr[k];
			}
			if (next is null)
			{
				Fail(id, "no '" + segs[i] + "' at path segment " + i + " of '" + path + "'");
				return;
			}
			@sv = next;
		}
		string text = SvalJson(sv, 0);
		auto j = Reply(id, true).Str("root", args[0]).Str("path", path).Int("chars", text.length());
		auto t = sv.GetType();
		if (t == SValueType::Dictionary)
		{
			auto keys = sv.GetDictionaryKeys();
			keys.sortAsc();
			j.Raw("keys", StrArray(keys));
		}
		else if (t == SValueType::Array)
			j.Int("length", sv.GetArray().length());
		if (text.length() <= INSPECT_CAP)
			j.Raw("value", text).Bool("truncated", false);
		else
			j.Bool("truncated", true);
		Emit(j);
	}

	// selftest-throw: dereferences null on purpose; proves ConsoleGl's catch (playbook 1.4)
	void VerbSelftestThrow(const string &in id, array<string>@ args)
	{
		PlayerRecord@ none = null;
		Emit(Reply(id, true).Str("name", none.name));
	}

	// player classes the fixture recipes can name
	void VerbClasses(const string &in id, array<string>@ args)
	{
		array<string> names;
		for (uint i = 0; i < PlayerClass::Instances.length(); i++)
		{
			if (PlayerClass::Instances[i].parent == 0)
				names.insertLast(PlayerClass::Instances[i].m_id);
		}
		Emit(Reply(id, true).Raw("classes", StrArray(names)));
	}

	// fixture verb: char <classId> <name>
	// The same steps as CreateCharacterWindow's "create" (GUI/CreateCharacterWindow.as:136-141)
	// without its pickers. CreateCharacter defaults the colours (PlayerRecord.as:468-471) but not
	// the portrait: an empty one null-derefs the vanilla dyer window (GetPortraitModel,
	// CreateCharacterCustomize.as:610; pets-dye 20261020-144606). So SetPortrait gets each
	// category's default piece after it.
	void VerbChar(const string &in id, array<string>@ args)
	{
		if (args.length() < 2)
		{
			Fail(id, "usage: char <classId> <name>");
			return;
		}
		auto gm = cast<AGameplayGameMode>(g_gameMode);
		if (gm is null)
		{
			Fail(id, "not in a gameplay game mode");
			return;
		}
		auto pClass = PlayerClass::Get(HashString(args[0]));
		if (pClass is null)
		{
			Fail(id, "no player class '" + args[0] + "' (gl <id> classes)");
			return;
		}
		if (PlayerVoice::Instances.length() == 0)
		{
			Fail(id, "no player voices loaded");
			return;
		}
		gm.SavePlayerAndTown();
		PlayerRecord@ plr = null;
		for (uint i = 0; i < g_players.length(); i++)
		{
			if (g_players[i].peer == 255 || !g_players[i].local)
				continue;
			@g_players[i] = PlayerRecord(g_players[i]);
			@plr = g_players[i];
			break;
		}
		if (plr is null)
		{
			Fail(id, "no local player record");
			return;
		}
		plr.CreateCharacter(pClass, args[1], PlayerVoice::Instances[0]);
		// CreateCharacter leaves the portrait empty; the vanilla dyer and HUD expect one piece per category.
		array<PlayerPortraitCategory> cats = { PlayerPortraitCategory::Class, PlayerPortraitCategory::Hair,
			PlayerPortraitCategory::Nose, PlayerPortraitCategory::Eyes, PlayerPortraitCategory::Mouth };
		array<PlayerPortraitPiece@> pieces;
		for (uint c = 0; c < cats.length(); c++)
		{
			auto piece = PlayerPortraitPiece::GetDefaultPiece(cats[c]);
			if (piece !is null)
				pieces.insertLast(piece);
		}
		if (pieces.length() > 0)
			plr.SetPortrait(pieces);
		gm.SpawnLocalPlayers();
		gm.m_windowManager.QueueClear();
		GetHUD().RefreshPortrait(plr);
		Emit(Reply(id, true).Str("class", pClass.m_id).Str("name", args[1]));
	}

	void RegisterBuiltins()
	{
		AddFunction("gl", { cvar_type::String }, ConsoleGl, 0, "GameLab command channel: gl <id> <verb> [args]");
		RegisterVerb("ping", "", Verb(VerbPing));
		RegisterVerb("multi", "<verb> [args] + <verb> [args] ...", Verb(VerbMulti));
		RegisterVerb("help", "", Verb(VerbHelp));
		RegisterVerb("state", "", Verb(VerbState));
		RegisterVerb("mods", "", Verb(VerbMods));
		RegisterVerb("ui", "", Verb(VerbUi));
		RegisterVerb("overlays", "", Verb(VerbOverlays));
		RegisterVerb("buildings", "", Verb(VerbBuildings));
		RegisterVerb("clock", "", Verb(VerbClock));
		RegisterVerb("widgets", "[depth] [root] [type]", Verb(VerbWidgets));
		RegisterVerb("terrain", "[radius] [step]", Verb(VerbTerrain));
		RegisterVerb("members", "<TypeName>", Verb(VerbMembers));
		RegisterVerb("inspect", "<player|town> [dotted.path]", Verb(VerbInspect));
		RegisterVerb("selftest-throw", "", Verb(VerbSelftestThrow));
		RegisterVerb("classes", "", Verb(VerbClasses));
		RegisterVerb("cvars", "<name>...", Verb(VerbCvars));
		RegisterVerb("inv", "", Verb(VerbInv));
		RegisterVerb("near", "[radius] [behaviorOrUnitName]", Verb(VerbNear));
		RegisterVerb("fetchbench", "<radius> [reps] [all|foes|units]", Verb(VerbFetchBench));
		RegisterVerb("traps", "[radius]", Verb(VerbTraps));
		RegisterVerb("bossbars", "", Verb(VerbBossBars));
		RegisterVerb("bubbles", "", Verb(VerbBubbles));
		RegisterVerb("areatriggers", "[radius]", Verb(VerbAreaTriggers));
		RegisterVerb("usables", "", Verb(VerbUsables));
		RegisterVerb("run", "", Verb(VerbRun));
		RegisterVerb("sval", "<file.sval>", Verb(VerbSval));
		RegisterVerb("char", "<classId> <name>", Verb(VerbChar));
	}
}

namespace Modules
{
	class GameLabProbeModule : Module
	{
		int m_sinceBeat = 0;
		uint m_frames = 0;
		uint m_beats = 0;
		int m_maxMs = 0;         // the longest frame since the last beat (a script stall shows here)
		uint m_beatFrames = 0;   // frames since the last beat

		GameLabProbeModule()
		{
			super("gamelab-probe");
			GameLab::RegisterBuiltins();
			GameLab::g_boots++;
			GameLab::Json j;
			j.Str("ev", "boot").Int("n", GameLab::g_boots).Str("version", GameLab::VERSION).Str("level", GetCurrentLevelFilename());
			GameLab::Emit(j);
		}

		void UpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused) override
		{
			// the command channel (Inbox.as): read every frame, paused ones too
			try {
				GameLab::InboxFrame();
			} catch {
				GameLab::g_exceptions++;
			}
			m_frames++;
			m_beatFrames++;
			GameLab::g_frames++;
			m_sinceBeat += ms;
			if (ms > m_maxMs)
				m_maxMs = ms;
			if (m_sinceBeat < 1000)
				return;
			m_sinceBeat = 0;
			m_beats++;
			// the heartbeat must not be able to break the frame (repro playbook 1.4)
			try {
				// place: every event after this beat belongs to it (the harness tags them,
				// gamelab/session.py); maxMs/beatFrames: a frame the scripts held for seconds
				// left no line at all (cube-run 20261018-222736: 15 silent gaps of ~24 s)
				GameLab::Json j;
				j.Str("ev", "hb").Int("n", m_beats).Int("frames", m_frames).Str("phase", GameLab::Phase())
					.Str("window", GameLab::TopWindow()).Bool("paused", paused).Int("cmds", GameLab::g_commands)
					.Int("exceptions", GameLab::g_exceptions).Str("place", GameLab::LevelPlace())
					.Int("maxMs", m_maxMs).Int("beatFrames", m_beatFrames)
					.Int("inLines", GameLab::g_inboxLines).Int("inDropped", GameLab::g_inboxDropped).Int("inDups", GameLab::g_inboxDups).Int("inScrubbed", GameLab::g_inboxScrubbed)
					.Bool("textIn", GameLab::InboxExpecting());
				m_maxMs = 0;
				m_beatFrames = 0;
				GameLab::Emit(j);
			} catch {
				GameLab::g_exceptions++;
			}
		}
	}
}
