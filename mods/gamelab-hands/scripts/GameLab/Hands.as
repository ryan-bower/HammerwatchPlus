// gamelab-hands: action verbs for the gl channel. Each verb calls the function
// the game's own UI calls for the same action, never a screen coordinate.
namespace GameLab
{
	// Generation seed for the floor `mission` starts.
	// - The generator draws from the global randi()/randf() (Generators/DungeonGenerator.as:400,
	//   434 and every brush/command); nothing in script seeds it.
	// - That RNG is shared with another thread while MissionGameMode::Generate runs
	//   (GameModes/MissionGameMode.as:424): srand(seed), a CPU-only spin, then randi() gives a
	//   different value on every load (seed-repeat 20261018-162919), and the engine draws from it
	//   every frame (rand-frames 20261018-161957). srand alone cannot replay a layout.
	// - So tools/make_seeded_generators.py overrides every Generators/*.as that draws, routing
	//   randi/randf/randdir/roll_round through GenRandi/GenRandf/GenRandDir/GenRollRound below:
	//   a private RandomSequence while g_genActive, the engine's own functions otherwise.
	// - Activation: Generate loads the town (:434), which fires TownRecordLoad
	//   (Town/TownRecord.as:446) before the floor's generator runs (:456). Script globals do not
	//   survive ChangeLevel (seed-repeat 20261018-160442), so the seed rides in the town save: the
	//   engine's SaveForLevelSwitch (AGameplayGameMode.as:864-867) saves the town and our
	//   TownRecordSave hook (TownRecord.as:380) adds GEN_SEED_KEY while g_genSeedPending.
	// - The sequence stays active through Start, so the generator-file draws there (enemy
	//   placement, DungeonGenerator.as:49-80, from MissionGameMode.as:314) are seeded too; the
	//   GameModeStart hook (AGameplayGameMode.as:226) also srands the global RNG with
	//   seed ^ GEN_SEED_START_XOR for RewardSpot and post-gen commands (best effort: same thread
	//   caveat), and re-saves the town without the key so later floors are random again. The
	//   module's first UpdateFrame turns the sequence off.
	const uint GEN_SEED_START_XOR = 0x5eed5eed;
	const string GEN_SEED_KEY = "gamelab-gen-seed";
	uint g_genSeed = 0;
	bool g_genSeedPending = false;   // this level: `mission` set a seed, the town save carries it
	bool g_genStartPending = false;  // this level: a load applied it, GameModeStart reseeds
	int g_genSeedApplied = 0;        // this level: town loads that carried the seed
	int g_genStartApplied = 0;       // this level: GameModeStart reseeds
	bool g_genActive = false;        // this level: generator draws come from g_genRng
	int g_genDraws = 0;              // this level: draws taken from g_genRng
	RandomSequence g_genRng;

	uint GenRandi()
{
		if (!g_genActive)
			return randi();
		g_genDraws++;
		return (uint(g_genRng.GetInt(65536)) << 16) | uint(g_genRng.GetInt(65536));
	}

	int GenRandi(int max)
	{
		if (!g_genActive)
			return randi(max);
		g_genDraws++;
		return max <= 0 ? 0 : g_genRng.GetInt(max);
	}

	// randi(min, max) is used once (DungeonBrush.as:612, randi(-1, 1)); max is taken as
	// inclusive here (assumed, not measured: only a 1-unit breakable jitter depends on it)
	int GenRandi(int lo, int hi)
	{
		if (!g_genActive)
			return randi(lo, hi);
		return hi <= lo ? lo : lo + GenRandi(hi - lo + 1);
	}

	float GenRandf()
	{
		if (!g_genActive)
			return randf();
		g_genDraws++;
		return g_genRng.GetFloat();
	}

	// randdir(bool unit = true) is native; seeded stand-in: a unit vector, or (unit false) a
	// point in the unit disc (assumed meaning of the flag; used for jitter and deco scatter)
	vec2 GenRandDir(bool unit = true)
	{
		if (!g_genActive)
			return randdir(unit);
		float a = GenRandf() * 6.2831853f;
		float r = unit ? 1.0f : sqrt(GenRandf());
		return vec2(cos(a) * r, sin(a) * r);
	}

	// roll_round (Utils/Functions.as:865-872) with GenRandf
	int GenRollRound(float f)
	{
		int v = abs(int(f));
		if (GenRandf() < (f - v))
			v++;
		return (f < 0) ? -v : v;
	}

	// mission <missionId> [floorIndex] [ngp] [seed=N] [ngp=N]: what the mission board's start does
	// (MissionManager::SetMission + StartMission, Missions/MissionManager.as:53-69); floor 0
	// when omitted. The floor is generated from seed N (uint; a random one when omitted),
	// applied as described at g_genSeed; the reply's "seed" replays the layout. A floor that
	// was preloaded (ChangeLevel's preloadId, MissionManager.as:68) is not regenerated, so
	// call it from town or from a different floor. `genseed` reports what was applied.
	// ngp=N sets g_ngp like the mission window's NG+ arrows (ShopContent/WindowMission.as:
	// 264-270: clamped to 0..the character's ngp); without it g_ngp stays what it is. The
	// reply's "ngp" is the g_ngp the mission starts with. A plain second number after the floor
	// sets g_ngp unclamped, as before seed= existed (the scenarios that pass [floor, ngp]).
	void VerbMission(const string &in id, array<string>@ args)
	{
		string usage = "usage: mission <missionId> [floorIndex] [ngp] [seed=N] [ngp=N]";
		if (args.length() < 1)
		{
			Fail(id, usage);
			return;
		}
		auto def = MissionDef::Get(args[0]);
		if (def is null)
		{
			Fail(id, "no mission '" + args[0] + "'");
			return;
		}
		int floor = 0;
		bool haveSeed = false;
		uint seed = 0;
		int positional = 0;
		for (uint i = 1; i < args.length(); i++)
		{
			if (args[i].findFirst("seed=") == 0)
			{
				uint used = 0;
				string num = args[i].substr(5);
				seed = uint(parseUInt(num, 10, used));
				if (num.isEmpty() || used != num.length())
				{
					Fail(id, "bad seed '" + num + "' (" + usage + ")");
					return;
				}
				haveSeed = true;
			}
			else if (args[i].findFirst("ngp=") == 0)
			{
				auto rec = GetLocalPlayerRecord();
				int cap = rec is null ? 0 : rec.ngp;
				g_ngp = float(max(0, min(cap, int(parseInt(args[i].substr(4))))));
			}
			else if (positional++ == 0)
				floor = int(parseInt(args[i]));
			else
				g_ngp = float(parseInt(args[i]));   // main's positional form: [floorIndex] [ngp]
		}
		if (floor < 0 || floor >= int(def.m_levels.length()))
		{
			Fail(id, "mission '" + args[0] + "' has " + def.m_levels.length() + " floor(s)");
			return;
		}
		if (!haveSeed)
			seed = randi();
		g_genSeed = seed;
		g_genSeedPending = true;
		Emit(Reply(id, true).Str("mission", args[0]).Int("floor", floor).Str("level", def.m_levels[floor].m_level)
			.Int("seed", seed).Bool("seedGiven", haveSeed).Int("ngp", int(g_ngp + 0.5f)));
		MissionManager::SetMission(HashString(args[0]), randi());
		MissionManager::g_module.m_missionLevelIndex = floor;
		MissionManager::g_module.StartMission();
	}

	// genseed: read-only. The generation seed this level was given by `mission` (0: none)
	// and how it was applied (see g_genSeed): "applied" counts town loads that carried it
	// (Generate and Start each load the town), "startApplied" the GameModeStart reseed,
	// "active" whether generator draws still come from the private sequence, "draws" how many
	// they took; "pending" true right after `mission`, before the level changes.
	void VerbGenSeed(const string &in id, array<string>@ args)
	{
		Emit(Reply(id, true).Int("seed", g_genSeed).Bool("pending", g_genSeedPending)
			.Bool("startPending", g_genStartPending).Int("applied", g_genSeedApplied)
			.Int("startApplied", g_genStartApplied).Bool("active", g_genActive).Int("draws", g_genDraws)
			.Str("level", GetCurrentLevelFilename()));
	}
}

namespace GameLab
{
	// randcheck <seed> [n] [seed|draw]: measurement only. srand(seed), then the first n
	// (default 4, at most 16) randi() and randi(1000) draws: does the script's srand drive the
	// global RNG the generator uses? "seed" only seeds, "draw" only draws (no srand), so a
	// later frame shows whether anything else drew in between.
	void VerbRandCheck(const string &in id, array<string>@ args)
	{
		if (args.length() < 1)
		{
			Fail(id, "usage: randcheck <seed> [n]");
			return;
		}
		uint seed = uint(parseUInt(args[0]));
		int n = args.length() > 1 ? int(parseInt(args[1])) : 4;
		if (n < 1)
			n = 1;
		if (n > 16)
			n = 16;
		string mode = args.length() > 2 ? args[2] : "";
		if (mode != "draw")
			srand(seed);
		if (mode == "seed")
		{
			Emit(Reply(id, true).Int("seed", seed).Str("mode", mode));
			return;
		}
		array<string> a, b;
		for (int i = 0; i < n; i++)
			a.insertLast("" + randi());
		for (int i = 0; i < n; i++)
			b.insertLast("" + randi(1000));
		RandomSequence rs;
		rs.SetSeed(seed);
		array<string> c;
		for (int i = 0; i < n; i++)
			c.insertLast("" + rs.GetInt(1000));
		Emit(Reply(id, true).Int("seed", seed).Raw("randi", RawArray(a)).Raw("randi1000", RawArray(b))
			.Raw("sequence1000", RawArray(c)));
	}
}

namespace GameLabGenSeed
{
	[Hook]
	void TownRecordSave(TownRecord@ town, SValueBuilder& builder)
	{
		if (GameLab::g_genSeedPending)
			builder.PushInteger(GameLab::GEN_SEED_KEY, int(GameLab::g_genSeed));
	}

	[Hook]
	void TownRecordLoad(TownRecord@ town, SValue@ save)
	{
		if (save is null || GameLab::g_genSeedPending)
			return;
		auto v = save.GetDictionaryEntry(GameLab::GEN_SEED_KEY);
		if (v is null || v.GetType() != SValueType::Integer)
			return;
		GameLab::g_genSeedApplied++;
		if (GameLab::g_genActive)
			return; // Start's LoadTown after Generate's: keep the sequence running
		GameLab::g_genSeed = uint(v.GetInteger());
		GameLab::g_genRng.SetSeed(GameLab::g_genSeed);
		GameLab::g_genActive = true;
		GameLab::g_genStartPending = true;
		print("[GameLab] gen seed " + GameLab::g_genSeed + " active (town load " + GameLab::g_genSeedApplied + ")");
	}

	[Hook]
	void GameModeStart(AGameplayGameMode@ gm, SValue@ save)
	{
		if (!GameLab::g_genStartPending)
			return;
		GameLab::g_genStartPending = false;
		GameLab::g_genStartApplied++;
		gm.SavePlayerAndTown(false);
		srand(GameLab::g_genSeed ^ GameLab::GEN_SEED_START_XOR);
		print("[GameLab] gen seed " + GameLab::g_genSeed + " start reseed (" + GameLab::g_genDraws + " generator draws so far)");
	}
}
namespace GameLab
{
	// pick [index]: play the index-th character of the open PickCharacterWindow,
	// through the window's own handler (OnFunc "play <key>"), like a click on Play.
	void VerbPick(const string &in id, array<string>@ args)
	{
		auto gm = cast<BaseGameMode>(g_gameMode);
		PickCharacterWindow@ win = null;
		if (gm !is null && gm.m_windowManager !is null)
		{
			for (uint i = 0; i < gm.m_windowManager.m_objects.length() && win is null; i++)
				@win = cast<PickCharacterWindow>(gm.m_windowManager.m_objects[i]);
		}
		if (win is null)
		{
			Fail(id, "PickCharacterWindow is not open (window: " + TopWindow() + ")");
			return;
		}
		int index = args.length() > 0 ? int(parseInt(args[0])) : 0;
		if (index < 0 || index >= int(win.m_list.m_children.length()))
		{
			Fail(id, "no character slot " + index + " (" + win.m_list.m_children.length() + " listed)");
			return;
		}
		auto slot = cast<CharacterPickWidget>(win.m_list.m_children[index]);
		if (slot is null)
		{
			Fail(id, "slot " + index + " is not a CharacterPickWidget");
			return;
		}
		uint key = slot.m_idHash;
		// A character saved inside a mission level gets the "run-resume" dialog
		// (PickCharacterWindow "play"). Answer it through the window's own handler instead:
		// "town" (default) = No, back to town; "resume" = Yes, back into the run.
		string choice = args.length() > 1 ? args[1] : "town";
		string run = PersistentSaves::GetCharacterLevelSaveName(key);
		Emit(Reply(id, true).Int("index", index).Int("key", key).Str("run", run).Str("choice", run.isEmpty() ? "" : choice));
		if (run.isEmpty() || !Network::IsServer())
		{
			win.OnFunc(slot, "play " + key);
			return;
		}
		win.m_resumingCharKey = key;
		win.OnFunc(slot, "run-resume " + (choice == "resume" ? "yes" : "no"));
	}
}

namespace GameLab
{
	// a wall between a and b; actors (the player, the pet, enemies) are not walls
	bool SpawnRayBlocked(vec2 a, vec2 b)
	{
		if (!g_scene.RaycastQuick(a, b, ~0, RaycastType::Any))
			return false;
		auto res = g_scene.Raycast(a, b, ~0, RaycastType::Any);
		if (res.length() == 0)
			return true;
		for (uint i = 0; i < res.length(); i++)
		{
			RaycastResult r = res[i];
			UnitPtr u = r.FetchUnit(g_scene);
			if (!u.IsValid() || cast<Actor>(u.GetScriptBehavior()) is null)
				return true;
		}
		return false;
	}

	// spawn <unitFile> <dx> <dy> [clear]: produce a unit at the player's position + (dx, dy),
	// the same UnitProducer.Produce call level scripts and actions use. "clear" turns the
	// offset 45 degrees a try (up to 8, then 8 more at half the offset) until the line from the
	// player to the spot is blocked by no wall (actors do not count), so a spawn in a narrow
	// path does not land in the trees beside it
	// (pets-mission 20261020-154008: a goblin at +70,0 in a north-south forest path was
	// out of reach and out of sight; the Pilot attack stood still 30 s)
	void VerbSpawn(const string &in id, array<string>@ args)
	{
		if (args.length() < 3)
		{
			Fail(id, "usage: spawn <unitFile> <dx> <dy> [clear]");
			return;
		}
		auto plr = GetLocalPlayer();
		if (plr is null)
		{
			Fail(id, "no spawned local player");
			return;
		}
		auto prod = Resources::GetUnitProducer(args[0]);
		if (prod is null)
		{
			Fail(id, "no unit '" + args[0] + "'");
			return;
		}
		vec3 from = plr.m_unit.GetPosition();
		vec2 off = vec2(parseFloat(args[1]), parseFloat(args[2]));
		bool clear = args.length() >= 4 && args[3] == "clear";
		int turns = 0;
		bool found = !clear;
		// the full offset first, then half of it (pets-mission 20261020-163326: the elite at
		// 70 px had no clear turn and the Pilot attack found it unreachable)
		for (int pass = 0; clear && !found && pass < 2; pass++)
		{
			vec2 o = pass == 0 ? off : off * 0.5f;
			for (int t = 0; t < 8 && !found; t++)
			{
				if (!SpawnRayBlocked(xy(from), xy(from) + o))
				{
					off = o;
					found = true;
				}
				else
				{
					o = vec2(0.7071f * (o.x - o.y), 0.7071f * (o.x + o.y));
					turns++;
				}
			}
		}
		vec3 pos = from + vec3(off.x, off.y, 0);
		UnitPtr u = prod.Produce(g_scene, pos);
		if (!u.IsValid())
		{
			Fail(id, "Produce returned an invalid unit");
			return;
		}
		auto r = Reply(id, true).Int("unit", u.GetId()).Str("name", u.GetDebugName()).Num("x", pos.x).Num("y", pos.y);
		if (clear)
			r.Int("turns", turns).Bool("clear", found);
		Emit(r);
	}

	// drop <type> <amount> <dx> <dy>: a material pickup at the player + (dx, dy) through
	// Material::DropMaterial, the call enemy loot and cht_spawn_gold use (Console/Cheats.as:906-911),
	// so it carries an amount (a unit from spawn holds 0). No drop animation: it lands where asked.
	void VerbDrop(const string &in id, array<string>@ args)
	{
		if (args.length() < 4)
		{
			Fail(id, "usage: drop <gold|wood|stone|iron|crystals|dust|ore> <amount> <dx> <dy>");
			return;
		}
		auto plr = GetLocalPlayer();
		if (plr is null)
		{
			Fail(id, "no spawned local player");
			return;
		}
		vec3 pos = plr.m_unit.GetPosition() + vec3(parseFloat(args[2]), parseFloat(args[3]), 0);
		UnitPtr u = Material::DropMaterial(ParseMaterialType(args[0]), parseInt(args[1]), pos, true, false);
		if (!u.IsValid())
		{
			Fail(id, "DropMaterial returned no unit (a client asks the host instead)");
			return;
		}
		Emit(Reply(id, true).Int("unit", u.GetId()).Str("name", u.GetDebugName()).Int("amount", parseInt(args[1])).Num("x", pos.x).Num("y", pos.y));
	}
}

namespace GameLab
{
	// build <buildingId>: what the town builder's "new" does (BuildingBuilderContent.Buy,
	// Town/BuildingBuilder.as) minus the cost and the cutscene: AddBuilding on a
	// buildable plot of the building's plot type (the first, where the game picks one
	// at random), then SavePlayerAndTown
	void VerbBuild(const string &in id, array<string>@ args)
	{
		if (args.length() < 1)
		{
			Fail(id, "usage: build <buildingId>");
			return;
		}
		auto gm = cast<AGameplayGameMode>(g_gameMode);
		if (gm is null || g_myTownRecord is null || !g_inTown)
		{
			Fail(id, "not in town");
			return;
		}
		auto def = BuildingManagement::BuildingDef::Get(HashString(args[0]));
		if (def is null)
		{
			Fail(id, "no building '" + args[0] + "'");
			return;
		}
		if (g_myTownRecord.GetVariationOnBuilding(def.m_idHash) >= 0)
		{
			Emit(Reply(id, true).Str("building", args[0]).Bool("existed", true));
			return;
		}
		WorldScript::BuildingPlot@ plot = null;
		if (def.m_plotHash != 0)
		{
			for (uint i = 0; i < g_myTownRecord.m_plots.length() && plot is null; i++)
			{
				if (def.m_plotHash == g_myTownRecord.m_plots[i].m_plotDefHash && g_myTownRecord.m_plots[i].IsBuildable())
					@plot = g_myTownRecord.m_plots[i];
			}
			if (plot is null)
			{
				Fail(id, "no buildable plot for '" + args[0] + "'");
				return;
			}
		}
		g_myTownRecord.AddBuilding(def, plot);
		gm.SavePlayerAndTown();
		Emit(Reply(id, true).Str("building", args[0]).Bool("existed", false)
			.Int("variation", g_myTownRecord.GetVariationOnBuilding(def.m_idHash)));
	}

	// townrefresh: what a building upgrade does once its cutscene ends
	// (TownRecord.Refresh, Town/TownRecord.as): QuickReloadLevel and SpawnTown in
	// the same scene, without a new Start, so mods see their units destroyed
	void VerbTownRefresh(const string &in id, array<string>@ args)
	{
		if (g_currTownRecord is null || !g_inTown || !Network::IsServer())
		{
			Fail(id, "not the host in town");
			return;
		}
		g_currTownRecord.Refresh();
		Emit(Reply(id, true));
	}

	// every TextWidget text under w, depth first (the menu verb's "texts")
	void CollectTexts(Widget@ w, array<string>@ acc)
	{
		auto t = cast<TextWidget>(w);
		if (t !is null)
			acc.insertLast(t.m_str);
		if (w.m_children is null)
			return;
		for (uint i = 0; i < w.m_children.length(); i++)
			CollectTexts(w.m_children[i], acc);
	}

	// the widget a "menu ... !click|!press" presses next, and whether it releases too
	AInteractableWidget@ g_pendingClick;
	int g_pendingClickMs = 0;
	bool g_pendingRelease = false;

	void UpdatePendingClick(int ms)
	{
		if (g_pendingClick is null)
			return;
		g_pendingClickMs -= ms;
		if (g_pendingClickMs > 0)
			return;
		g_pendingClick.ClickDown(false, vec2());
		if (g_pendingRelease)
			g_pendingClick.ClickUp(false, vec2());
		@g_pendingClick = null;
	}

	// menu [tab] [subtab|-] [widget] [func...]: open the player menu the way its key does
	// (HWR2GameMode::TogglePlayerMenu, when it is not open yet), then press the
	// tab buttons: PlayerMenu::OnFunc("set-tab <tab>") and the open tab's own
	// OnFunc("set-tab <subtab>") (the character tab's sub-tab checkboxes, e.g.
	// material-inventory; "-" for none). Replies with the open tab's class. [widget]: a
	// widget id in that tab: scrolls its scrollbar to the end, replies shown (it and every
	// parent visible), its size, its "count" text (the core hwp-material cells) and every
	// text under it in "texts" (joined with " | "); a textinput adds "input" and "typing". [func...]: first the open tab's
	// OnFunc(<func>) as if a button with that func was clicked (e.g. "hwp-opt colors");
	// "!click" instead presses [widget] itself the way the window does on use
	// (AInteractableWidget.ClickDown: a textinput starts taking typed text), 250 ms
	// later: this command arrives through the console, whose closing would end the
	// text input a click started while it was open. "!press" clicks it fully (ClickDown
	// then ClickUp), for widgets that act on the release (core's hwp-material cells).
	void VerbMenu(const string &in id, array<string>@ args)
	{
		auto gm = cast<HWR2GameMode>(g_gameMode);
		if (gm is null)
		{
			Fail(id, "not in a gameplay mode");
			return;
		}
		PlayerMenu@ menu = null;
		for (uint i = 0; i < gm.m_windowManager.m_objects.length() && menu is null; i++)
			@menu = cast<PlayerMenu>(gm.m_windowManager.m_objects[i]);
		if (menu is null)
		{
			gm.TogglePlayerMenu();
			for (uint i = 0; i < gm.m_windowManager.m_objects.length() && menu is null; i++)
				@menu = cast<PlayerMenu>(gm.m_windowManager.m_objects[i]);
		}
		if (menu is null)
		{
			Fail(id, "the player menu did not open (another window is up?)");
			return;
		}
		if (args.length() > 0)
			menu.OnFunc(null, "set-tab " + args[0]);
		auto tabs = menu.m_tabSystem;
		MenuTab@ tab = tabs.m_tabs[tabs.m_currentIndex];
		if (args.length() > 1 && args[1] != "-")
			tab.OnFunc(null, "set-tab " + args[1]);
		if (args.length() > 3 && (args[3] == "!click" || args[3] == "!press"))
		{
			auto iw = cast<AInteractableWidget>(tab.m_widget.GetWidgetById(args[2]));
			if (iw is null)
			{
				Fail(id, "no interactable widget '" + args[2] + "' to click");
				return;
			}
			@g_pendingClick = iw;
			g_pendingClickMs = 250;
			g_pendingRelease = args[3] == "!press";
		}
		else if (args.length() > 3)
		{
			string func = args[3];
			for (uint i = 4; i < args.length(); i++)
				func += " " + args[i];
			tab.OnFunc(null, func);
		}
		Json@ r = Reply(id, true).Str("tab", Reflect::GetTypeName(tab)).Int("index", tabs.m_currentIndex);
		// [widget]: find it in the tab, scroll its scrollbar to the end (where our sections
		// sit) and report whether it and every parent are visible, plus its "count" text
		if (args.length() > 2)
		{
			Widget@ w = tab.m_widget.GetWidgetById(args[2]);
			if (w is null)
			{
				Fail(id, "no widget '" + args[2] + "' in " + Reflect::GetTypeName(tab));
				return;
			}
			bool shown = true;
			for (Widget@ p = w; p !is null; @p = p.m_parent)
			{
				shown = shown && p.m_visible;
				auto sb = cast<ScrollbarWidget>(p);
				if (sb !is null)
					sb.m_handleValue = 1.0f;
			}
			auto count = cast<TextWidget>(w.GetWidgetById("count"));
			array<string> texts;
			CollectTexts(w, texts);
			r.Str("widget", args[2]).Bool("shown", shown).Int("w", w.m_width).Int("h", w.m_height)
				.Str("count", count !is null ? count.m_str : "").Str("texts", join(texts, " | "));
			auto ti = cast<TextInputWidget>(w);
			if (ti !is null)
				r.Str("input", ti.m_text.plain()).Bool("typing", ti.m_typing);
		}
		Emit(r);
	}

	// save: the game's own SavePlayerAndTown (what the builder, the shops and leaving
	// town call), so the next session loads this town instead of a null one
	void VerbSave(const string &in id, array<string>@ args)
	{
		auto gm = cast<AGameplayGameMode>(g_gameMode);
		if (gm is null)
		{
			Fail(id, "not in a gameplay game mode");
			return;
		}
		gm.SavePlayerAndTown();
		Emit(Reply(id, true));
	}
}

namespace Modules
{
	class GameLabHandsModule : Module
	{
		GameLabHandsModule()
		{
			super("gamelab-hands");
			GameLab::RegisterVerb("spawn", "<unitFile> <dx> <dy>", GameLab::Verb(GameLab::VerbSpawn));
			GameLab::RegisterVerb("pick", "[index] [town|resume]", GameLab::Verb(GameLab::VerbPick));
			GameLab::RegisterVerb("mission", "<missionId> [floorIndex] [ngp] [seed=N] [ngp=N]", GameLab::Verb(GameLab::VerbMission));
			GameLab::RegisterVerb("genseed", "", GameLab::Verb(GameLab::VerbGenSeed));
			GameLab::RegisterVerb("randcheck", "<seed> [n] [seed|draw]", GameLab::Verb(GameLab::VerbRandCheck));
			GameLab::RegisterVerb("build", "<buildingId>", GameLab::Verb(GameLab::VerbBuild));
			GameLab::RegisterVerb("townrefresh", "", GameLab::Verb(GameLab::VerbTownRefresh));
			GameLab::RegisterVerb("save", "", GameLab::Verb(GameLab::VerbSave));
			GameLab::RegisterVerb("menu", "[tab] [subtab|-] [widget] [func...]", GameLab::Verb(GameLab::VerbMenu));
			GameLab::RegisterVerb("xp", "<amount>", GameLab::Verb(GameLab::VerbXp));
			GameLab::RegisterVerb("material", "<type|all> <n>", GameLab::Verb(GameLab::VerbMaterial));
			GameLab::RegisterVerb("cheats", "[on|off]", GameLab::Verb(GameLab::VerbCheats));
			GameLab::RegisterVerb("levelup", "<n>", GameLab::Verb(GameLab::VerbLevelup));
			GameLab::RegisterVerb("points", "<skill|stat> <n>", GameLab::Verb(GameLab::VerbPoints));
			GameLab::RegisterVerb("ngp", "<n>", GameLab::Verb(GameLab::VerbNgp));
			GameLab::RegisterVerb("setup", "<file>", GameLab::Verb(GameLab::VerbSetup));
			GameLab::RegisterVerb("charflag", "<name>", GameLab::Verb(GameLab::VerbCharFlag));
			GameLab::RegisterVerb("subclass", "<classId>", GameLab::Verb(GameLab::VerbSubclass));
			GameLab::RegisterVerb("classskills", "<classId>", GameLab::Verb(GameLab::VerbClassSkills));
			GameLab::RegisterVerb("skill", "<skillId> [times] [combo]", GameLab::Verb(GameLab::VerbSkill));
			GameLab::RegisterVerb("skillup", "<skillId> [n|max]", GameLab::Verb(GameLab::VerbSkillUp));
			GameLab::RegisterVerb("mastery", "<masteryId> [n|all]", GameLab::Verb(GameLab::VerbMastery));
			GameLab::RegisterVerb("kill", "<radius> <filter> [hp|me]", GameLab::Verb(GameLab::VerbKill));
			GameLab::RegisterVerb("abort", "[failed]", GameLab::Verb(GameLab::VerbAbort));
			GameLab::RegisterVerb("combo", "", GameLab::Verb(GameLab::VerbCombo));
			// test-plan verbs, one file per plan group (Verbs_<group>.as)
			GameLab::Register_classesa();
			GameLab::Register_classesb();
			GameLab::Register_farming();
			GameLab::Register_firearms();
			GameLab::Register_fishing();
			GameLab::Register_gear();
			GameLab::Register_newa();
			GameLab::Register_newb();
			GameLab::Register_pets();
			GameLab::Register_runs();
			GameLab::Register_specs();
			GameLab::Register_qa_resources();
			GameLab::Register_qa_actor_buffs();
			GameLab::Register_qa_routeleg();
			GameLab::Register_qa_input_sequence();
			GameLab::Register_qa_input_target();
			GameLab::Register_qa_spheres();
			GameLab::Register_qa_damage_fields();
			GameLab::Register_qa_trigger_payload();
			GameLab::Register_qa_class_projectile();
			GameLab::Register_qa_skill_cost();
			GameLab::Register_ui();
			GameLab::RegisterVerb("assign", "<str|dex|int|foc|vit> <n|all>", GameLab::Verb(GameLab::VerbAssign));
			GameLab::RegisterVerb("upgrade", "<shopId> <upgradeId> <step>", GameLab::Verb(GameLab::VerbUpgrade));
			GameLab::RegisterVerb("equip", "<baseItemId> <quality> [ilvl]", GameLab::Verb(GameLab::VerbEquip));
			GameLab::RegisterVerb("stashitem", "<baseItemId> <quality> [ilvl]", GameLab::Verb(GameLab::VerbStashItem));
			GameLab::RegisterVerb("stash", "[tab]", GameLab::Verb(GameLab::VerbStash));
			GameLab::RegisterVerb("drop", "<type> <amount> <dx> <dy>", GameLab::Verb(GameLab::VerbDrop));
			GameLab::RegisterVerb("press", "<widgetId>", GameLab::Verb(GameLab::VerbPress));
			GameLab::RegisterVerb("func", "<name...>", GameLab::Verb(GameLab::VerbFunc));
			GameLab::RegisterVerb("charcreate", "", GameLab::Verb(GameLab::VerbCharCreate));
			GameLab::RegisterVerb("use", "<filter>", GameLab::Verb(GameLab::VerbUse));
			GameLab::RegisterVerb("shoplevel", "<filter> <level>", GameLab::Verb(GameLab::VerbShopLevel));
			GameLab::RegisterVerb("shop", "[buy <index>]", GameLab::Verb(GameLab::VerbShop));
			GameLab::RegisterVerb("trinkets", "", GameLab::Verb(GameLab::VerbTrinkets));
			GameLab::RegisterVerb("prefab", "<file> <dx> <dy>", GameLab::Verb(GameLab::VerbPrefab));
			GameLab::RegisterVerb("ws", "<type> [commentPrefix]", GameLab::Verb(GameLab::VerbWs));
			GameLab::RegisterVerb("usews", "<comment> [ifType ifComment]", GameLab::Verb(GameLab::VerbUseWs));
			GameLab::RegisterVerb("goto", "<type> <comment> [dx dy]", GameLab::Verb(GameLab::VerbGoto));
			GameLab::RegisterVerb("timescale", "<x>", GameLab::Verb(GameLab::VerbTimescale));
			GameLab::RegisterVerb("cull", "[mine]", GameLab::Verb(GameLab::VerbCull));
			GameLab::RegisterVerb("teleport", "<x> <y>", GameLab::Verb(GameLab::VerbTeleport));
			GameLab::RegisterVerb("controller", "", GameLab::Verb(GameLab::VerbController));
			GameLab::RegisterVerb("setvar", "<name> <value...>", GameLab::Verb(GameLab::VerbSetVar));
			GameLab::RegisterVerb("cheat", "<ply_kill|cht_revive|cht_set_flag|cht_give_material|mission_start> [args]", GameLab::Verb(GameLab::VerbCheat));
			GameLab::RegisterVerb("input", "<ms> <mx> <my> [aimX aimY] [button,button]", GameLab::Verb(GameLab::VerbInput));
		}

		void UpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused) override
		{
			if (GameLab::g_genActive)
			{
				GameLab::g_genActive = false; // the floor is built and populated: vanilla RNG again
				print("[GameLab] gen seed " + GameLab::g_genSeed + " done (" + GameLab::g_genDraws + " generator draws)");
			}
			GameLab::SeeInput(gameInput);
			GameLab::UpdatePendingClick(ms);
			if (!paused)
				GameLab::ApplyHeld(ms, gameInput);
		}
	}
}
