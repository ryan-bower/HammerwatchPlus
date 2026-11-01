// gamelab-pilot: the player bot's in-engine half. gamelab/pilot.py drives it.
//
// One intent runs at a time, stepped from GameLabPilotModule.UpdateFrame. It steers
// through the emulated controller in gamelab-hands (GameLab::WriteInput: GameInput.MoveDir,
// AimDir, buttons), so the player's own code moves, attacks and uses things. No OS input.
//
//   gl <id> pilot <intent> [args] [until=a,b:50] [timeout=ms]
//     intents: move x y [tol] | path_to x y [tol] | attack <unit|nearest> (actor or Breakable) | kite <unit|nearest> [range]
//              | use [unit] | potion | wait ms | exit
//   gl <id> pilot pause | resume | step [frames] | target <unit> | stop | status
//   gl <id> scan [radius]
//
// The verb replies at once ({"accepted": intent}). The intent's end is one event with the
// same id: {"ev":"pilot","id":...,"result":"done|failed|timeout|interrupted|no_route","reason":...}.
// While an intent runs, {"ev":"ptick","tick":n,...} goes out every PTICK_EVERY frames; the tick
// number is what watch-mode feedback cites.
//
// Interrupts are a closed vocabulary (INTERRUPTS); anything else is refused. level_changed
// cannot fire in here: a level load reloads the script module and this state with it
// (docs/RE_NOTES.md), so gamelab/pilot.py reports it from the probe's boot event.
namespace GameLab
{
	const array<string> INTERRUPTS = { "hp_below", "under_attack", "target_dead", "level_changed", "menu_open", "dead" };
	const array<string> INTENTS = { "move", "path_to", "attack", "kite", "use", "potion", "wait", "exit" };
	const int PTICK_EVERY = 6;
	const int PATH_DIAMETER = 12;
	const float MELEE_RANGE = 22.0f;
	const int ENGAGE = 180;        // attack/kite "nearest" retargets only this close; none left = done

	class PilotIntent
	{
		string id;
		string kind;
		vec2 goal;
		float tol = 10.0f;
		array<vec2>@ path;
		uint wp = 0;
		UnitPtr target;
		bool nearest = false;
		float range = 0;
		int timeoutMs = 30000;
		int elapsed = 0;
		array<string> until;
		float hpBelow = -1;
		int prevHp = -1;
		int pulses = 0;
		int sincePulse = 100000;
		int sincePath = 100000;
		int sinceDash = 100000;
		bool approaching = false;      // attack/kite/use: closing in on the target this frame
		vec2 lastPos;                  // FollowPath: last frame's position (the slide test)
		bool escaped = false;
		bool partial = false;          // exit: the path ends at the reached point nearest the exit
		int partialHops = 0;          // exit: the route starts at a RouteStart point, not here
		int wiggleMs = 0;              // exit: stepping out of a wedge before routing again
		vec2 wiggleDir;
		array<int> skip;               // attack/kite "nearest": targets given up on (unreachable)
		int potionsUsed0 = 0;
		vec2 stuckFrom;
		int stuckMs = 0;
		int repaths = 0;
		int frames = 0;
		vec2 anchor;                   // exit: where to stand (the area sensor; ExitStandPoint)
		WorldScript@ exitWs;
		bool areaFound = false;
		bool pushing = false;          // exit: at the approach point, steering into the area
		vec2 approach;                 // exit: walkable point nearest the anchor
		bool hasApproach = false;
		bool nav = false;              // exit: the route came from NavRoute
		int navExpanded = 0;
		// Only path_to with an original finite 0 < tol <= 2 uses this controller.
		// Bounds are cumulative for the intent; no engine velocity conversion is assumed.
		bool tight = false, tightHolding = false, tightForeign = false;
		vec2 tightGoal, tightExpectedMove, tightPrevious;
		float tightTol = 0, tightStepPeak = 0, tightCap = 1;
		float tightPulseCredit = 0; // cap is callback duty; writes remain unit direction or zero
		int tightBoots = 0, tightPlayer = 0, tightNow = 0;
		string tightLevel;
		Scene@ tightScene;
		PlayerRecord@ tightRecord;
		PlayerBase@ tightActor;
		array<GameInput@> tightInputs;
		array<bool> tightPads;
		uint tightWrites = 0;
		int tightCorrections = 0, tightHolds = 0, tightQuiet = 0, tightInsideQuiet = 0, tightNeutral = 0;
		int tightObservations = 0, tightNoMotion = 0;
		// Diagnostic state only. No controller field is read from these values.
		int tightDiagEntries = 0, tightDiagRecords = 0, tightDiagDropped = 0;
		bool tightDiagInvalid = false, tightDiagTruncated = false;
		TightProbe@ tightDiagLastGuard;
	}

	PilotIntent@ g_intent;
	bool g_pilotPaused = false;
	int g_pilotSteps = 0;          // frames to run while paused (step)
	uint g_tick = 0;               // pilot frames run in this level (a level load resets it)

	// Read-only, at most five observations of one tight path_to arrival. This
	// callback counter is NOT an engine actor/physics phase or g_tick clock.
	uint g_arrivalCallbacks = 0;
	string g_arrivalId, g_arrivalLevel;
	int g_arrivalPlayer = 0, g_arrivalBoots = 0, g_arrivalSeen = 0, g_arrivalTail = 0;
	int g_arrivalDt = 0;
	bool g_arrivalPaused = false;
	bool ArrivalFinite(float value) { return value == value && value >= -1000000 && value <= 1000000; }

	string ArrivalInput(GameInput@ input)
	{
		if (input is null) return "null";
		if (!ArrivalFinite(input.MoveDir.x) || !ArrivalFinite(input.MoveDir.y)) return "null";
		int slot = -1; // Looking up an existing handle never registers one.
		for (uint i = 0; i < g_inputs.length(); i++)
			if (g_inputs[i] is input) { slot = int(i); break; }
		array<string> down;
		if (input.Use.Down) down.insertLast("use");
		if (input.Potion.Down) down.insertLast("potion");
		if (input.Dash.Down) down.insertLast("dash");
		if (input.MainHandAttack.Down) down.insertLast("main");
		if (input.OffHandAttack.Down) down.insertLast("off");
		if (input.Skill1.Down) down.insertLast("skill1");
		if (input.Skill2.Down) down.insertLast("skill2");
		if (input.Skill3.Down) down.insertLast("skill3");
		Json row;
		row.Int("slot", slot).Num("mx", input.MoveDir.x).Num("my", input.MoveDir.y)
			.Bool("gamepad", input.UsingGamepad).Raw("down", StrArray(down));
		return row.Close();
	}

	void ArrivalProbeAbort(const string &in reason)
	{
		if (!g_arrivalId.isEmpty() && g_arrivalSeen < 5)
		{
			Json row;
			Emit(row.Str("id", g_arrivalId).Str("ev", "path_arrival_probe").Str("phase", "abort")
				.Int("sample", g_arrivalSeen).Int("planned", 5).Bool("complete", false).Str("reason", reason));
		}
		g_arrivalId = ""; g_arrivalTail = 0;
	}

	void ArrivalProbeSample(GameInput& callbackInput, const string &in phase, bool complete)
	{
		if (g_arrivalId.isEmpty()) return;
		auto player = GetLocalPlayer();
		auto record = GetLocalPlayerRecord();
		if (player is null || record is null || !record.local || record.actor !is player
			|| !player.m_unit.IsValid() || player.IsDead() || player.m_unit.GetId() != g_arrivalPlayer
			|| g_boots != g_arrivalBoots || GetCurrentLevelFilename() != g_arrivalLevel
			|| g_players.length() > 16 || g_inputs.length() > MAX_INPUTS || g_arrivalSeen >= 5)
		{ ArrivalProbeAbort("unavailable or changed sole actor/world/input bounds"); return; }
		for (uint i = 0; i < g_players.length(); i++)
			if (g_players[i] !is null && g_players[i] !is record)
			{ ArrivalProbeAbort("another player record"); return; }
		auto body = player.m_unit.GetPhysicsBody();
		if (body is null) { ArrivalProbeAbort("body unavailable"); return; }
		vec2 velocity = body.GetLinearVelocity(); // read only, no physics setter
		vec3 pos = player.m_unit.GetPosition();
		if (!ArrivalFinite(velocity.x) || !ArrivalFinite(velocity.y) || !ArrivalFinite(pos.x)
			|| !ArrivalFinite(pos.y) || !ArrivalFinite(pos.z))
		{ ArrivalProbeAbort("nonfinite/unbounded native motion observation"); return; }
		auto current = GetInput();
		GameInput@ callback = callbackInput;
		array<string> buffers;
		for (uint i = 0; i < g_inputs.length(); i++) buffers.insertLast(ArrivalInput(g_inputs[i]));
		Json row;
		row.Str("id", g_arrivalId).Str("ev", "path_arrival_probe").Str("phase", phase)
			.Int("sample", g_arrivalSeen).Int("planned", 5).Bool("complete", complete)
			.Int("callback", g_arrivalCallbacks).Int("pilot_tick", g_tick).Int("dt", g_arrivalDt).Bool("paused", g_arrivalPaused)
			.Int("now", int(g_scene.GetTime())).Int("probe_frames", g_frames).Int("boots", g_boots)
			.Int("player", g_arrivalPlayer).Str("level", g_arrivalLevel)
			.Num("x", pos.x).Num("y", pos.y).Num("z", pos.z).Num("vx", velocity.x).Num("vy", velocity.y)
			.Raw("callback_input", ArrivalInput(callback)).Raw("current_input", ArrivalInput(current))
			.Bool("callback_is_current", current is callback).Raw("buffers", RawArray(buffers))
			.Int("input_writes", g_inputFrames).Bool("release_pending", g_releasePending)
			.Int("release_calls_left", g_releaseFrames).Str("held_owner", g_held.owner)
			.Int("held_ms", g_held.msLeft).Raw("held_buttons", StrArray(g_held.buttons))
			.Str("skillkeys_held", GlobalCache::Get(SKILLKEYS_HELD)).Bool("sequence_busy", g_qaInputSequenceBusy)
			.Num("reflex_fire", g_reflexFire).Num("reflex_potion", g_reflexPotion)
			.Str("active_intent", g_intent is null ? "" : g_intent.id)
			.Str("scope", "Pilot callback observations only; no actor/physics phase or causal conclusion");
		if (row.Close().length() > 12000) { ArrivalProbeAbort("diagnostic emit cap"); return; }
		Emit(row);
		g_arrivalSeen++;
		if (complete) g_arrivalId = "";
	}

	void BeginArrivalProbe(PilotIntent@ it, GameInput& input)
	{
		if (it.tol > 2) return; // unchanged tight path_to requests only
		if (!g_arrivalId.isEmpty()) ArrivalProbeAbort("superseded before complete");
		g_arrivalId = it.id; g_arrivalSeen = 0; g_arrivalTail = 3;
		g_arrivalPlayer = GetLocalPlayer().m_unit.GetId();
		g_arrivalBoots = g_boots; g_arrivalLevel = GetCurrentLevelFilename();
		try { ArrivalProbeSample(input, "pre_neutral", false); }
		catch { ArrivalProbeAbort("diagnostic read exception"); }
	}

	void AfterArrivalProbe(GameInput& input)
	{
		try { ArrivalProbeSample(input, "post_neutral", false); }
		catch { ArrivalProbeAbort("diagnostic read exception"); }
	}

	void AdvanceArrivalProbe(int ms, GameInput& input, bool paused)
	{
		g_arrivalCallbacks++; g_arrivalDt = ms; g_arrivalPaused = paused;
		if (g_arrivalId.isEmpty() || g_arrivalTail <= 0) return;
		if (g_intent !is null && g_intent.id != g_arrivalId)
		{ ArrivalProbeAbort("another intent before observation complete"); return; }
		string phase = "future" + (4 - g_arrivalTail);
		g_arrivalTail--;
		try { ArrivalProbeSample(input, phase, g_arrivalTail == 0); }
		catch { ArrivalProbeAbort("diagnostic read exception"); }
	}

	Actor@ ActorOf(UnitPtr u)
	{
		if (!u.IsValid() || u.IsDestroyed())
			return null;
		return cast<Actor>(u.GetScriptBehavior());
	}

	// an actor until it dies, or a Breakable until it is destroyed: debris piles are static
	// collision with no nav-block opt-out, so they close passages until smashed (floor-soak
	// 20261017-192513: castle_debris_pile_wood_noloot at 0,904 beside the cut at -125,971)
	bool TargetGone(UnitPtr u)
	{
		if (!u.IsValid() || u.IsDestroyed())
			return true;
		auto a = ActorOf(u);
		if (a !is null)
			return a.IsDead();
		return cast<Breakable>(u.GetScriptBehavior()) is null;
	}

	UnitPtr NearestEnemy(vec2 from, int radius, array<int>@ skip = null)
	{
		auto units = g_scene.FetchActorsWithOtherTeam(g_team_player, from, radius);
		UnitPtr best;
		float bestD = 1e9;
		for (uint i = 0; i < units.length(); i++)
		{
			auto a = ActorOf(units[i]);
			if (a is null || a.IsDead() || !a.IsTargetable())
				continue;
			if (skip !is null && skip.find(units[i].GetId()) >= 0)
				continue;
			float d = dist(from, xy(units[i].GetPosition()));
			if (d < bestD)
			{
				bestD = d;
				best = units[i];
			}
		}
		return best;
	}

	// Where to stand to take an exit. A LevelExitAreaNext fires only for a player inside one
	// of its CollisionAreas, and the area is not at the exit unit: on dark_citadel floor 0 it is
	// a sensor 140 units off (unit + (-72,-120)); standing on the unit is outside it, standing
	// on the sensor is inside, the exit is the top usable and Use loads the next floor
	// (exit-areas 20261017-162406, -162451; pilot-crosslevel 20261017-161523 stood on the unit
	// for 6 minutes). The area exposes no position, so: the centroid of the units it reports
	// inside, then the sensor unit (QueryCircle getSensors) nearest that centroid.
	vec2 ExitStandPoint(WorldScript@ ws, bool &out found)
	{
		vec2 at = xy(ws.GetUnit().GetPosition());
		found = false;
		auto ex = cast<WorldScript::LevelExitAreaNext>(ws.GetUnit().GetScriptBehavior());
		if (ex is null || ex.Areas is null)
			return at;
		vec2 c;
		int n = 0;
		for (uint i = 0; i < ex.Areas.length(); i++)
		{
			if (ex.Areas[i] is null)
				continue;
			auto inside = ex.Areas[i].FetchAllInside(g_scene);
			for (uint k = 0; inside !is null && k < inside.length(); k++)
			{
				if (!inside[k].IsValid() || inside[k].GetId() == 0)
					continue;
				c += xy(inside[k].GetPosition());
				n++;
			}
		}
		if (n == 0)
			return at;
		c = c / float(n);
		auto withS = g_scene.QueryCircle(at, 600, ~0, RaycastType::Any, true);
		auto without = g_scene.QueryCircle(at, 600, ~0, RaycastType::Any, false);
		vec2 best = c;
		float bestD = 1e9;
		for (uint i = 0; i < withS.length(); i++)
		{
			if (withS[i].GetDebugName().findFirst(":Physics") != 0)
				continue;
			bool plain = false;
			for (uint k = 0; k < without.length() && !plain; k++)
				plain = without[k] == withS[i];
			if (plain)
				continue;
			float d = dist(c, xy(withS[i].GetPosition()));
			if (d < bestD)
			{
				bestD = d;
				best = xy(withS[i].GetPosition());
			}
		}
		found = true;
		return best;
	}

	bool InExitArea(WorldScript@ ws, UnitPtr u)
	{
		auto ex = cast<WorldScript::LevelExitAreaNext>(ws.GetUnit().GetScriptBehavior());
		if (ex is null || ex.Areas is null)
			return false;
		for (uint i = 0; i < ex.Areas.length(); i++)
			if (ex.Areas[i] !is null && ex.Areas[i].IsInside(u))
				return true;
		return false;
	}

	WorldScript@ NearestExit(vec2 from)
	{
		WorldScript@ best = null;
		float bestD = 1e9;
		array<string> types = { "LevelExitAreaNext", "LevelExitNext" };
		for (uint t = 0; t < types.length(); t++)
		{
			auto list = g_scene.FetchAllWorldScripts(types[t]);
			for (uint i = 0; i < list.length(); i++)
			{
				if (!list[i].IsEnabled())
					continue;
				float d = dist(from, xy(list[i].GetUnit().GetPosition()));
				if (d < bestD)
				{
					bestD = d;
					@best = list[i];
				}
			}
		}
		return best;
	}

	// Observation only. A foreign/unknown owner must not schedule a later neutral
	// writer. Inactive HeldInput configuration is history, not an active writer.
	bool TightButtonsClear(GameInput@ input)
	{
		return input !is null && !input.Use.Down && !input.Use.Pressed
			&& !input.Potion.Down && !input.Potion.Pressed && !input.Dash.Down && !input.Dash.Pressed
			&& !input.MainHandAttack.Down && !input.MainHandAttack.Pressed
			&& !input.OffHandAttack.Down && !input.OffHandAttack.Pressed
			&& !input.Skill1.Down && !input.Skill1.Pressed && !input.Skill2.Down && !input.Skill2.Pressed
			&& !input.Skill3.Down && !input.Skill3.Pressed;
	}

	// Fixed small observation cache. "unobserved" is never a neutral/default value.
	class TightProbeInput
	{
		string nullSeen = "\"unobserved\"", handleSame = "\"unobserved\"";
		string pad = "\"unobserved\"", savedPad = "\"unobserved\"";
		string mx = "\"unobserved\"", my = "\"unobserved\"";
		int downSeen = 0, downTrue = 0, pressedSeen = 0, pressedTrue = 0;
		string Raw()
		{
			Json j; j.Raw("null", nullSeen).Raw("handle_same", handleSame).Raw("pad", pad).Raw("saved_pad", savedPad)
				.Raw("mx", mx).Raw("my", my).Int("down_seen", downSeen).Int("down_true", downTrue)
				.Int("pressed_seen", pressedSeen).Int("pressed_true", pressedTrue);
			return j.Close();
		}
	}
	class TightProbe
	{
		string location, phase, first, now = "\"unobserved\"", player = "\"unobserved\"";
		string owner = "\"unobserved\"", writer = "\"unobserved\"", callbackSame = "\"unobserved\"";
		string operandActual = "\"unobserved\"", operandExpected = "\"unobserved\"";
		string guardWrites = "\"unobserved\"", guardExpectedWrites = "\"unobserved\"";
		string expectedX, expectedY, plannedX = "\"unobserved\"", plannedY = "\"unobserved\"";
		int callback = 0, frame = 0, boots = 0, entry = 0, writes = 0, expectedWrites = 0;
		int currentSlot = -1, callbackSlot = -1, failedSlot = -1;
		string heldMs = "\"unobserved\"";
		bool invalid = false;
		array<TightProbeInput@> inputs;
		TightProbe() { for (uint i = 0; i < MAX_INPUTS; i++) inputs.insertLast(TightProbeInput()); }
	}
	string TightProbeBool(bool value) { return value ? "true" : "false"; }
	string TightProbeFloat(double value)
	{
		return value == value && value >= -1000000 && value <= 1000000 ? formatFloat(value, "", 0, 9) : "null";
	}
	string TightProbeNumber(TightProbe@ p, double value)
	{
		if (!(value == value && value >= -1000000 && value <= 1000000)) p.invalid = true;
		return TightProbeFloat(value);
	}
	void TightProbeInit(PilotIntent@ it, TightProbe@ p, const string &in location, const string &in phase, vec2 planned)
	{
		p.location = location; p.phase = phase; p.callback = int(g_arrivalCallbacks); // ordering, NOT physics phase
		p.frame = g_frames; p.boots = g_boots; p.entry = it.tightDiagEntries;
		p.writes = g_inputFrames; p.expectedWrites = it.tightWrites;
		p.expectedX = TightProbeNumber(p,it.tightExpectedMove.x); p.expectedY = TightProbeNumber(p,it.tightExpectedMove.y);
		if (location == "pre_write" || phase == "post_write")
		{ p.plannedX = TightProbeNumber(p,planned.x); p.plannedY = TightProbeNumber(p,planned.y); }
		// One explicitly new metadata read, before guard evaluation, never retried in a handler.
		try { if (g_scene !is null) { int now = int(g_scene.GetTime()); p.now = "" + now; if (now < 0) p.invalid = true; } else p.invalid = true; }
		catch { p.invalid = true; }
	}
	string TightProbeAt(TightProbe@ p, int slot)
	{
		return slot >= 0 && slot < int(p.inputs.length()) ? p.inputs[slot].Raw() : "\"unobserved\"";
	}
	void TightProbeEmit(PilotIntent@ it, TightProbe@ p)
	{
		// No Native/Input/actor getter is called here: failures use only the cache.
		try
		{
			if (it.tightDiagRecords >= 16) { it.tightDiagDropped++; it.tightDiagTruncated = true; it.tightDiagInvalid = true; return; }
			// No "id": admit-time events must not steal gl_cmd's first matching reply.
			Json j; j.Str("intent_id", it.id).Str("ev", "tight_input_probe").Int("seq", it.tightDiagRecords + 1)
				.Str("location", p.location).Str("phase", p.phase).Str("first_failed", p.first)
				.Str("binding_source", p.phase == "post_write" ? "preceding guard cache; NEW input readback" : "original guard operands; marker inputs unobserved")
				.Bool("valid", !p.invalid).Str("later_predicates", "unobserved after first failure")
				.Int("callback", p.callback).Int("entry", p.entry).Int("frame", p.frame).Raw("now", p.now)
				.Int("boots", p.boots).Int("expected_boots", it.tightBoots).Raw("player", p.player).Int("expected_player", it.tightPlayer)
				.Raw("owner_binding_ok", p.owner).Raw("writer_guard_ok", p.writer).Raw("callback_same", p.callbackSame)
				.Int("writes_at_start", p.writes).Int("expected_writes", p.expectedWrites).Raw("held_ms", p.heldMs)
				.Raw("guard_writes", p.guardWrites).Raw("guard_expected_writes", p.guardExpectedWrites)
				.Raw("expected_x", p.expectedX).Raw("expected_y", p.expectedY).Raw("planned_x", p.plannedX).Raw("planned_y", p.plannedY)
				.Int("current_slot", p.currentSlot).Int("callback_slot", p.callbackSlot)
				.Int("failed_slot", p.failedSlot).Raw("guard_actual", p.operandActual).Raw("guard_expected", p.operandExpected)
				.Raw("current", TightProbeAt(p, p.currentSlot)).Raw("callback_input", TightProbeAt(p, p.callbackSlot))
				.Raw("slot0", TightProbeAt(p, 0)).Raw("failed_input", TightProbeAt(p, p.failedSlot))
				.Int("window_entries", 3).Int("record_cap", 16).Int("char_cap", 3000);
			if (j.Close().length() > 3000) { it.tightDiagDropped++; it.tightDiagTruncated = true; it.tightDiagInvalid = true; return; }
			// Separate bounded log event: do not alter Emit's in-engine reply-capture buffer.
			print("[GL] " + j.Close()); it.tightDiagRecords++;
			if (p.invalid) it.tightDiagInvalid = true;
		}
		catch { it.tightDiagDropped++; it.tightDiagInvalid = true; }
	}
	bool TightProbeFail(TightProbe@ p, const string &in code, bool failed, int slot = -1)
	{
		if (failed && p.first.isEmpty()) { p.first = code; p.failedSlot = slot; }
		return failed;
	}
	bool TightProbeButton(TightProbe@ p, TightProbeInput@ row, int bit, bool pressed, bool value, const string &in code, int slot)
	{
		if (pressed) { row.pressedSeen |= bit; if (value) row.pressedTrue |= bit; }
		else { row.downSeen |= bit; if (value) row.downTrue |= bit; }
		if (code != "") TightProbeFail(p, code, value, slot); return !value;
	}
	bool TightProbeButtons(TightProbe@ p, TightProbeInput@ row, GameInput@ input, int slot)
	{
		// The original TightButtonsClear short-circuit order and getter count.
		return input !is null
			&& TightProbeButton(p,row,1,false,input.Use.Down,"use.down",slot) && TightProbeButton(p,row,1,true,input.Use.Pressed,"use.pressed",slot)
			&& TightProbeButton(p,row,2,false,input.Potion.Down,"potion.down",slot) && TightProbeButton(p,row,2,true,input.Potion.Pressed,"potion.pressed",slot)
			&& TightProbeButton(p,row,4,false,input.Dash.Down,"dash.down",slot) && TightProbeButton(p,row,4,true,input.Dash.Pressed,"dash.pressed",slot)
			&& TightProbeButton(p,row,8,false,input.MainHandAttack.Down,"main.down",slot) && TightProbeButton(p,row,8,true,input.MainHandAttack.Pressed,"main.pressed",slot)
			&& TightProbeButton(p,row,16,false,input.OffHandAttack.Down,"off.down",slot) && TightProbeButton(p,row,16,true,input.OffHandAttack.Pressed,"off.pressed",slot)
			&& TightProbeButton(p,row,32,false,input.Skill1.Down,"skill1.down",slot) && TightProbeButton(p,row,32,true,input.Skill1.Pressed,"skill1.pressed",slot)
			&& TightProbeButton(p,row,64,false,input.Skill2.Down,"skill2.down",slot) && TightProbeButton(p,row,64,true,input.Skill2.Pressed,"skill2.pressed",slot)
			&& TightProbeButton(p,row,128,false,input.Skill3.Down,"skill3.down",slot) && TightProbeButton(p,row,128,true,input.Skill3.Pressed,"skill3.pressed",slot);
	}
	string TightProbeReturn(PilotIntent@ it, TightProbe@ p, const string &in reason)
	{
		if (p.invalid) it.tightDiagInvalid = true;
		if (reason == "tight actor/world ownership changed or unavailable") p.owner = "false";
		if (reason == "tight foreign writer, release, skill key or write counter") p.writer = "false";
		if (p.first == "callback_handle") p.callbackSame = "false";
		p.phase = reason == "" ? "guard_pass" : "guard_fail";
		@it.tightDiagLastGuard = p; // bounded scalar cache only; contains no native handles
		if (reason != "" || p.location == "admit" || p.location == "admit_after_route" || it.tightDiagEntries <= 3)
			TightProbeEmit(it, p);
		return reason;
	}
	void TightProbeReadback(PilotIntent@ it, GameInput@ callback, vec2 planned)
	{
		if (it.tightDiagEntries > 3) return;
		TightProbe p; TightProbeInit(it,p,"tight_write","post_write",planned);
		// NEW readback only, after the existing write AND tracker update. Never
		// substitutes for a guard, updates expected state, or rescues ownership.
		try
		{
			if (it.tightDiagLastGuard !is null)
			{ p.player = it.tightDiagLastGuard.player; p.owner = it.tightDiagLastGuard.owner; p.writer = it.tightDiagLastGuard.writer; }
			auto current = GetInput(); p.callbackSame = TightProbeBool(current is callback);
			if (current is null || callback is null) p.invalid = true;
			if (g_inputs.length() > MAX_INPUTS) { p.invalid = true; TightProbeEmit(it,p); return; }
			for (uint i = 0; i < g_inputs.length(); i++)
			{
				auto input = g_inputs[i];
				if (input is current) p.currentSlot = int(i); if (input is callback) p.callbackSlot = int(i);
				if (i != 0 && input !is current && input !is callback) continue;
				TightProbeInput@ row = p.inputs[i]; row.nullSeen = TightProbeBool(input is null);
				if (input is null) { p.invalid = true; continue; }
				row.handleSame = TightProbeBool(i < it.tightInputs.length() && input is it.tightInputs[i]);
				row.pad = TightProbeBool(input.UsingGamepad);
				if (i < it.tightPads.length()) row.savedPad = TightProbeBool(it.tightPads[i]);
				row.mx = TightProbeNumber(p,input.MoveDir.x); row.my = TightProbeNumber(p,input.MoveDir.y);
				// Explicit NEW post-write observations; all buttons sampled even if one is down.
				bool ignored = TightProbeButton(p,row,1,false,input.Use.Down,"",int(i)); ignored = TightProbeButton(p,row,1,true,input.Use.Pressed,"",int(i));
				ignored = TightProbeButton(p,row,2,false,input.Potion.Down,"",int(i)); ignored = TightProbeButton(p,row,2,true,input.Potion.Pressed,"",int(i));
				ignored = TightProbeButton(p,row,4,false,input.Dash.Down,"",int(i)); ignored = TightProbeButton(p,row,4,true,input.Dash.Pressed,"",int(i));
				ignored = TightProbeButton(p,row,8,false,input.MainHandAttack.Down,"",int(i)); ignored = TightProbeButton(p,row,8,true,input.MainHandAttack.Pressed,"",int(i));
				ignored = TightProbeButton(p,row,16,false,input.OffHandAttack.Down,"",int(i)); ignored = TightProbeButton(p,row,16,true,input.OffHandAttack.Pressed,"",int(i));
				ignored = TightProbeButton(p,row,32,false,input.Skill1.Down,"",int(i)); ignored = TightProbeButton(p,row,32,true,input.Skill1.Pressed,"",int(i));
				ignored = TightProbeButton(p,row,64,false,input.Skill2.Down,"",int(i)); ignored = TightProbeButton(p,row,64,true,input.Skill2.Pressed,"",int(i));
				ignored = TightProbeButton(p,row,128,false,input.Skill3.Down,"",int(i)); ignored = TightProbeButton(p,row,128,true,input.Skill3.Pressed,"",int(i));
			}
			if (p.currentSlot < 0 || p.callbackSlot < 0 || g_inputs.length() == 0) p.invalid = true;
		}
		catch { p.invalid = true; }
		TightProbeEmit(it,p);
	}

	// Only movement readback: one local binary32 spacing, never more than 2^-24.
	// Unit-range finite values only; zero and sign changes remain exact refusals.
	// No conversion, getter retry, expected-state update or normalization here.
	bool TightMoveComponentSame(double actual, double expected)
	{
		if (!(actual >= -1 && actual <= 1 && expected >= -1 && expected <= 1)) return false;
		if (actual == expected) return true;
		if (actual == 0 || expected == 0 || (actual < 0) != (expected < 0)) return false;
		double a = actual < 0 ? -actual : actual, e = expected < 0 ? -expected : expected;
		double magnitude = a > e ? a : e;
		double gap = 0.000000059604644775390625, edge = 0.5; // 2^-24, half unit
		// At a binade edge use the smaller inward spacing; subnormal floor 2^-149.
		for (uint bit = 0; bit < 125 && magnitude <= edge; bit++) { gap *= 0.5; edge *= 0.5; }
		double difference = actual > expected ? actual - expected : expected - actual;
		return difference <= gap;
	}

	string TightOwnerReason(PilotIntent@ it, GameInput@ callback, const string &in location, vec2 planned = vec2())
	{
		TightProbe p; TightProbeInit(it, p, location, "before_guard", planned);
		if (location == "frame_entry" && it.tightDiagEntries <= 3) TightProbeEmit(it, p);
		auto rec = GetLocalPlayerRecord();
		auto actor = GetLocalPlayer();
		if (TightProbeFail(p,"record_null",rec is null) || TightProbeFail(p,"actor_null",actor is null)
			|| TightProbeFail(p,"record_handle",rec !is it.tightRecord) || TightProbeFail(p,"actor_handle",actor !is it.tightActor)
			|| TightProbeFail(p,"record_local",!rec.local) || TightProbeFail(p,"record_actor",rec.actor !is actor)
			|| TightProbeFail(p,"unit_invalid",!actor.m_unit.IsValid()))
			return TightProbeReturn(it,p,"tight actor/world ownership changed or unavailable");
		int playerId = actor.m_unit.GetId(); p.player = "" + playerId;
		if (TightProbeFail(p,"unit_id",playerId != it.tightPlayer) || TightProbeFail(p,"scene_handle",g_scene !is it.tightScene)
			|| TightProbeFail(p,"boots",g_boots != it.tightBoots) || TightProbeFail(p,"level",GetCurrentLevelFilename() != it.tightLevel))
			return TightProbeReturn(it,p,"tight actor/world ownership changed or unavailable");
		p.owner = "true";
		if (TightProbeFail(p,"player_bound",g_players.length() > 16)) return TightProbeReturn(it,p,"tight player bound");
		for (uint i = 0; i < g_players.length(); i++)
			if (TightProbeFail(p,"other_player",g_players[i] !is null && g_players[i] !is rec)) return TightProbeReturn(it,p,"tight sole player changed");
		int heldMs = g_held.msLeft; p.heldMs = "" + heldMs;
		if (TightProbeFail(p,"held_positive",heldMs > 0) || TightProbeFail(p,"sequence_busy",g_qaInputSequenceBusy)
			|| TightProbeFail(p,"reflex_fire",g_reflexFire > 0) || TightProbeFail(p,"reflex_potion",g_reflexPotion > 0)
			|| TightProbeFail(p,"skillkeys",!GlobalCache::Get(SKILLKEYS_HELD).isEmpty()) || TightProbeFail(p,"releasing",Releasing()))
			return TightProbeReturn(it,p,"tight foreign writer, release, skill key or write counter");
		uint observedWrites = g_inputFrames; uint expectedWrites = it.tightWrites;
		p.guardWrites = "" + observedWrites; p.guardExpectedWrites = "" + expectedWrites;
		if (TightProbeFail(p,"write_counter",observedWrites != expectedWrites) || TightProbeFail(p,"write_bound",g_inputFrames >= uint(2000000000)))
			return TightProbeReturn(it,p,"tight foreign writer, release, skill key or write counter");
		p.writer = "true";
		auto current = GetInput();
		if (TightProbeFail(p,"current_null",current is null) || TightProbeFail(p,"callback_null",callback is null)
			|| TightProbeFail(p,"callback_handle",current !is callback) || TightProbeFail(p,"inputs_empty",g_inputs.length() == 0)
			|| TightProbeFail(p,"inputs_bound",g_inputs.length() > MAX_INPUTS) || TightProbeFail(p,"inputs_count",g_inputs.length() != it.tightInputs.length()))
			return TightProbeReturn(it,p,"tight current/callback or remembered input bound changed");
		p.callbackSame = "true";
		bool found = false;
		for (uint i = 0; i < g_inputs.length(); i++)
		{
			auto input = g_inputs[i];
			TightProbeInput@ row = p.inputs[i]; row.nullSeen = TightProbeBool(input is null);
			// Reference aliases only: no getter/pointer/token registration or handler reread.
			if (input is current) p.currentSlot = int(i); if (input is callback) p.callbackSlot = int(i);
			if (TightProbeFail(p,"input_null",input is null,int(i))) return TightProbeReturn(it,p,"tight untracked, changed or non-owned input");
			bool same = input is it.tightInputs[i]; row.handleSame = TightProbeBool(same);
			if (TightProbeFail(p,"saved_input_handle",!same,int(i)) || !TightProbeButtons(p,row,input,int(i)))
				return TightProbeReturn(it,p,"tight untracked, changed or non-owned input");
			bool pad = input.UsingGamepad; bool expectedPad = it.tightPads[i]; row.pad = TightProbeBool(pad); row.savedPad = TightProbeBool(expectedPad);
			if (TightProbeFail(p,"gamepad",pad != expectedPad,int(i))) return TightProbeReturn(it,p,"tight untracked, changed or non-owned input");
			auto x = input.MoveDir.x; auto expectedX = it.tightExpectedMove.x; bool differentX = !TightMoveComponentSame(x,expectedX); row.mx = TightProbeNumber(p,x);
			if (TightProbeFail(p,"move_x",differentX,int(i)))
			{ p.operandActual = TightProbeNumber(p,x); p.operandExpected = TightProbeNumber(p,expectedX); return TightProbeReturn(it,p,"tight untracked, changed or non-owned input"); }
			auto y = input.MoveDir.y; auto expectedY = it.tightExpectedMove.y; bool differentY = !TightMoveComponentSame(y,expectedY); row.my = TightProbeNumber(p,y);
			if (TightProbeFail(p,"move_y",differentY,int(i)))
			{ p.operandActual = TightProbeNumber(p,y); p.operandExpected = TightProbeNumber(p,expectedY); return TightProbeReturn(it,p,"tight untracked, changed or non-owned input"); }
			if (input is current) found = true;
		}
		TightProbeFail(p,"current_untracked",!found);
		return TightProbeReturn(it,p,found ? "" : "tight current input untracked");
	}

	void PilotEnd(const string &in result, const string &in reason)
	{
		if (g_intent is null)
			return;
		Json j;
		j.Str("ev", "pilot").Str("id", g_intent.id).Str("intent", g_intent.kind).Str("result", result)
			.Str("reason", reason).Int("tick", g_tick).Int("ms", g_intent.elapsed).Int("frames", g_intent.frames);
		auto plr = GetLocalPlayer();
		if (plr !is null && (!g_intent.tight || plr.m_unit.IsValid()))
		{
			vec3 pos = plr.m_unit.GetPosition();
			j.Num("x", pos.x).Num("y", pos.y);
		}
		auto rec = GetLocalPlayerRecord();
		if (rec !is null)
			j.Int("hp", rec.CurrentHealth()).Int("hpMax", rec.MaxHealth());
		bool release = true;
		if (g_intent.tight)
		{
			// Fail closed if the read itself fails; do not clear foreign state either.
			release = false;
			try { release = !g_intent.tightForeign && TightOwnerReason(g_intent, GetInput(), "end_owner") == ""; }
			catch { g_intent.tightDiagInvalid = true; } // cache unavailable; no getter retry/recovery
			j.Bool("tight", true).Bool("release_scheduled", release)
				.Bool("holding", g_intent.tightHolding).Bool("foreign_observed", g_intent.tightForeign)
				.Int("corrections", g_intent.tightCorrections).Int("hold_observations", g_intent.tightHolds)
				.Int("quiet_observations", g_intent.tightQuiet).Int("inside_quiet_observations", g_intent.tightInsideQuiet)
				.Int("neutral_writes", g_intent.tightNeutral)
				.Int("observations", g_intent.tightObservations).Int("scene_now", g_intent.tightNow)
				.Num("world_step_peak", g_intent.tightStepPeak).Num("input_cap", g_intent.tightCap)
				.Bool("pulse_control", true).Num("pulse_credit", g_intent.tightPulseCredit)
				.Int("diag_entries", g_intent.tightDiagEntries).Int("diag_records", g_intent.tightDiagRecords)
				.Int("diag_dropped", g_intent.tightDiagDropped).Bool("diag_truncated", g_intent.tightDiagTruncated)
				.Bool("diag_invalid", g_intent.tightDiagInvalid);
		}
		@g_intent = null;
		if (release) g_releasePending = true; // existing default for all other intents
		Emit(j);
	}

	// a fresh engine path from the player to the intent's goal; false = no route. When one
	// Pathfind call answers empty: a target that is solid (a chest, a statue) gets a path to a
	// point around it (RouteNear); then NavRoute, partial, because a long route can answer
	// empty although the floor is one region (see Exit routing below). Town arrival (1984,598)
	// to the chapel courtyard answered empty in plan-t7 20261018-054309.
	bool Repath(PilotIntent@ it, vec2 from)
	{
		@it.path = g_scene.Pathfind(from, it.goal, PATH_DIAMETER);
		it.wp = 0;
		if (it.path !is null && it.path.length() > 0)
			return true;
		vec2 goal = it.goal;
		if (it.target.IsValid() && RouteNear(it, from, goal))
			return true;
		// a start in an obstacle's footprint (where a chest just opened, plan-t7 20261018-061257)
		// answers empty for every goal: route from a step out instead
		for (int k = 0; k < 8; k++)
		{
			float a = k * 3.14159265f / 4;
			vec2 step = from + vec2(cos(a), sin(a)) * 24;
			if (TryPath(it, step, goal) || (it.target.IsValid() && RouteNear(it, step, goal)))
			{
				it.goal = goal;
				return true;
			}
		}
		@it.path = NavRoute(from, goal, true);
		it.goal = goal;
		it.wp = 0;
		return it.path !is null && it.path.length() > 0;
	}

	// Exit routing. Measured on dark_citadel forest floors:
	// - Pathfind to the exit unit's own position always answers empty: it sits off the walkable
	//   area, and so do points 48-128 around it (pathfind-probe 20261017-153509). Where to stand
	//   is ExitStandPoint (the exit's area sensor).
	// - A long route can answer empty although both legs of it answer: player -> midpoint and
	//   midpoint -> exit (pathfind-probe 20261017-153509). Whole-floor reachmaps from the spawn
	//   and from beside the exit share cells (gap-walk 20261017-160053), so the floor is one
	//   region that one Pathfind call does not always cross. maxDistance/maxRange change
	//   neither (pathfind-probe 20261017-153815). Greedy waypoint hops dead-ended
	//   (pilot-crosslevel 20261017-162608).
	// So: one Pathfind call when it answers, else NavRoute: A* over a coarse grid whose edges
	// are short Pathfind calls between neighbouring cells, the legs stitched into one path.
	const float SLIDE_PROBE = 18;          // PathFollower: unit radius * 2
	const float WIGGLE_PROBE = 32;
	const int WIGGLE_MS = 400;
	const float NAV_STEP = 96;
	// the grid spans +-NAV_R cells around the start: 9216 at the coarse step. 64 (6144) missed a
	// spawn-to-exit distance of 6850 (pilot-crosslevel 20261017-171409)
	const int NAV_R = 96;
	const int NAV_W = 2 * NAV_R + 1;
	const int NAV_MAX_EXPAND = 4000;
	const float OPEN_REACH = 96;
	int g_navExpanded = 0;

	bool PathOk(vec2 from, vec2 to)
	{
		auto path = g_scene.Pathfind(from, to, PATH_DIAMETER);
		return path !is null && path.length() > 0;
	}

	// a point the pathfinder can stand on: a short path leaves it in some direction
	bool Walkable(vec2 p)
	{
		return PathOk(p, p + vec2(32, 0)) || PathOk(p, p + vec2(-32, 0))
			|| PathOk(p, p + vec2(0, 32)) || PathOk(p, p + vec2(0, -32));
	}

	// Walkable and not a nav island: paths reach OPEN_REACH out in at least two of eight
	// directions. A Walkable point can sit on an island no route leaves (route-sweep
	// 20261017-185821: a point by the exit, walkable, NavRoute expanded 3 cells; floor-soak
	// 20261017-184334: the exit's stand point, stand -> anywhere in 3 expansions).
	bool Open(vec2 p)
	{
		int n = 0;
		for (int k = 0; k < 8 && n < 2; k++)
		{
			float a = k * 3.14159265f / 4;
			if (PathOk(p, p + vec2(cos(a), sin(a)) * OPEN_REACH))
				n++;
		}
		return n >= 2;
	}

	class NavHeap
	{
		array<float> f;
		array<int> k;

		bool Empty() { return f.length() == 0; }

		void Swap(uint a, uint b)
		{
			float tf = f[a]; f[a] = f[b]; f[b] = tf;
			int tk = k[a]; k[a] = k[b]; k[b] = tk;
		}

		void Push(float pf, int pk)
		{
			f.insertLast(pf);
			k.insertLast(pk);
			uint i = f.length() - 1;
			while (i > 0)
			{
				uint p = (i - 1) / 2;
				if (f[p] <= f[i])
					break;
				Swap(p, i);
				i = p;
			}
		}

		int Pop()
		{
			int top = k[0];
			uint last = f.length() - 1;
			Swap(0, last);
			f.removeLast();
			k.removeLast();
			uint n = f.length();
			uint i = 0;
			while (true)
			{
				uint l = 2 * i + 1;
				uint r = l + 1;
				uint m = i;
				if (l < n && f[l] < f[m])
					m = l;
				if (r < n && f[r] < f[m])
					m = r;
				if (m == i)
					break;
				Swap(m, i);
				i = m;
			}
			return top;
		}
	}

	vec2 NavCell(vec2 from, int key, float step)
	{
		return from + vec2(key / NAV_W - NAV_R, key % NAV_W - NAV_R) * step;
	}

	// A* from `from` to `to` over grid cells NAV_STEP apart; null when no route within
	// NAV_MAX_EXPAND expansions. The result is the stitched engine path.
	// partial: when `to` is not reached, the route to the reached cell nearest it instead (if
	// that is at least two cells nearer than `from`), and g_navPartial set
	bool g_navPartial = false;

	array<vec2>@ NavRouteStep(vec2 from, vec2 to, float step, bool partial = false)
	{
		g_navPartial = false;
		int best = -1;
		float bestD = dist(from, to) - step * 2;
		int n = NAV_W * NAV_W;
		array<float> g(n, 1e9);
		array<int> parent(n, -1);
		array<bool> closed(n, false);
		int start = NAV_R * NAV_W + NAV_R;
		g[start] = 0;
		NavHeap open;
		open.Push(dist(from, to), start);
		int goal = -1;
		g_navExpanded = 0;
		while (!open.Empty() && g_navExpanded < NAV_MAX_EXPAND)
		{
			int k = open.Pop();
			if (closed[k])
				continue;
			closed[k] = true;
			g_navExpanded++;
			vec2 c = NavCell(from, k, step);
			if (dist(c, to) < bestD)
			{
				bestD = dist(c, to);
				best = k;
			}
			if (dist(c, to) <= step * 2 && PathOk(c, to))
			{
				goal = k;
				break;
			}
			int ci = k / NAV_W - NAV_R;
			int cj = k % NAV_W - NAV_R;
			for (int di = -1; di <= 1; di++)
				for (int dj = -1; dj <= 1; dj++)
				{
					int ni = ci + di;
					int nj = cj + dj;
					if ((di == 0 && dj == 0) || abs(ni) > NAV_R || abs(nj) > NAV_R)
						continue;
					int nk = (ni + NAV_R) * NAV_W + (nj + NAV_R);
					float ng = g[k] + ((di != 0 && dj != 0) ? step * 1.4142f : step);
					if (closed[nk] || ng >= g[nk])
						continue;
					vec2 nc = NavCell(from, nk, step);
					if (!PathOk(c, nc))
						continue;
					g[nk] = ng;
					parent[nk] = k;
					open.Push(ng + dist(nc, to), nk);
				}
		}
		if (goal < 0 && (!partial || best < 0))
			return null;
		g_navPartial = goal < 0;
		if (g_navPartial)
			goal = best;
		array<vec2> cells;
		for (int k = goal; k >= 0 && k != start; k = parent[k])
			cells.insertLast(NavCell(from, k, step));
		cells.reverse();
		if (!g_navPartial)
			cells.insertLast(to);
		array<vec2> path;
		vec2 prev = from;
		for (uint i = 0; i < cells.length(); i++)
		{
			auto leg = g_scene.Pathfind(prev, cells[i], PATH_DIAMETER);
			if (leg is null || leg.length() == 0)
				path.insertLast(cells[i]);
			else
				for (uint m = 0; m < leg.length(); m++)
					path.insertLast(leg[m]);
			prev = cells[i];
		}
		return path;
	}

	// NavRouteStep on a coarse grid first, then finer ones: a narrow passage between two coarse
	// cells' centres can be missed (pilot-crosslevel 20261017-164521: 381 expansions, no route)
	array<vec2>@ NavRoute(vec2 from, vec2 to, bool partial = false)
	{
		array<float> steps = { NAV_STEP, 64, 48 };
		int total = 0;
		for (uint i = 0; i < steps.length(); i++)
		{
			auto route = NavRouteStep(from, to, steps[i]);
			total += g_navExpanded;
			if (route !is null)
			{
				g_navExpanded = total;
				return route;
			}
		}
		if (partial)
		{
			auto route = NavRouteStep(from, to, NAV_STEP, true);
			g_navExpanded = total;
			return route;
		}
		g_navExpanded = total;
		g_navPartial = false;
		return null;
	}

	bool TryPath(PilotIntent@ it, vec2 from, vec2 to)
	{
		auto path = g_scene.Pathfind(from, to, PATH_DIAMETER);
		if (path is null || path.length() == 0)
			return false;
		@it.path = path;
		it.wp = 0;
		it.goal = to;
		return true;
	}

	// a target standing where the pathfinder cannot (in a tree's footprint): path to the
	// nearest point around it that answers; false (and it.path null) when none does
	bool RouteNear(PilotIntent@ it, vec2 pos, vec2 tp)
	{
		array<float> rings = { 32, 64, 96, 128 };
		for (uint r = 0; r < rings.length(); r++)
			for (int k = 0; k < 8; k++)
			{
				float a = k * 3.14159265f / 4;
				if (TryPath(it, pos, tp + vec2(cos(a), sin(a)) * rings[r]))
				{
					it.goal = tp;      // FollowPath ends on the target, the path leads around it
					return true;
				}
			}
		@it.path = null;
		return false;
	}

	// the approach point: the stand point if the pathfinder can stand there, else the
	// walkable ring point nearest it (the player then walks straight in)
	bool FindApproach(PilotIntent@ it, vec2 pos)
	{
		if (Open(it.anchor))
		{
			it.approach = it.anchor;
			return true;
		}
		array<float> rings = { 48, 96, 160, 224, 320, 448 };
		float base = atan(pos.y - it.anchor.y, pos.x - it.anchor.x);
		for (uint r = 0; r < rings.length(); r++)
			for (int k = 0; k < 16; k++)
			{
				// ring points facing the player first
				float a = base + ((k % 2 == 0) ? 1 : -1) * ((k + 1) / 2) * 3.14159265f / 8;
				vec2 c = it.anchor + vec2(cos(a), sin(a)) * rings[r];
				if (Open(c))
				{
					it.approach = c;
					return true;
				}
			}
		return false;
	}

	// Where routing starts. A player hugging trees or rocks can stand where the nav data is
	// blocked although the physics let it in; no Pathfind leaves such a spot (pilot-crosslevel
	// 20261017-165255: open field to the south, NavRoute expanded 3 cells). Then: the nearest
	// walkable point it can step to in a straight line (no raycast hit), toward `toward` first.
	bool RouteStart(vec2 pos, vec2 toward, vec2 &out start)
	{
		start = pos;
		if (Open(pos))
			return true;
		array<float> rings = { 16, 32, 48, 64, 96 };
		float base = atan(toward.y - pos.y, toward.x - pos.x);
		for (uint r = 0; r < rings.length(); r++)
			for (int k = 0; k < 16; k++)
			{
				float a = base + ((k % 2 == 0) ? 1 : -1) * ((k + 1) / 2) * 3.14159265f / 8;
				vec2 c = pos + vec2(cos(a), sin(a)) * rings[r];
				if (!g_scene.RaycastQuick(pos, c, ~0, RaycastType::Any) && Open(c))
				{
					start = c;
					return true;
				}
			}
		return false;
	}

	const int NAV_POCKET = 16;             // NavRoute total expansions under this: a pocket
	const int POCKET_TRIES = 12;

	array<vec2>@ RouteFromPocket(vec2 pos, vec2 to, vec2 &out start)
	{
		start = pos;
		array<float> rings = { 24, 48, 72, 96, 128 };
		float base = atan(to.y - pos.y, to.x - pos.x);
		int tries = 0;
		for (uint r = 0; r < rings.length() && tries < POCKET_TRIES; r++)
			for (int k = 0; k < 16 && tries < POCKET_TRIES; k++)
			{
				float a = base + ((k % 2 == 0) ? 1 : -1) * ((k + 1) / 2) * 3.14159265f / 8;
				vec2 c = pos + vec2(cos(a), sin(a)) * rings[r];
				if (g_scene.RaycastQuick(pos, c, ~0, RaycastType::Any) || !Walkable(c))
					continue;
				tries++;
				auto route = NavRouteStep(c, to, NAV_STEP);
				if (route !is null && route.length() > 0)
				{
					start = c;
					return route;
				}
			}
		return null;
	}

	const int PARTIAL_HOPS = 6;

	bool RouteExit(PilotIntent@ it, vec2 pos)
	{
		it.pushing = false;
		it.tol = 16.0f;
		if (!it.hasApproach)
		{
			it.hasApproach = FindApproach(it, pos);
			if (!it.hasApproach)
				return false;
		}
		vec2 start;
		if (!RouteStart(pos, it.approach, start))
			start = pos;
		it.escaped = dist(start, pos) > 0.5f;
		array<vec2>@ route = g_scene.Pathfind(start, it.approach, PATH_DIAMETER);
		it.nav = false;
		if (route is null || route.length() == 0)
		{
			@route = NavRoute(start, it.approach);
			it.navExpanded = g_navExpanded;
			it.nav = true;
		}
		if ((route is null || route.length() == 0) && it.navExpanded < NAV_POCKET)
		{
			// a pocket: the nav data around the player is closed off although it is walkable
			// (on a pond's bank between trees: pilot-crosslevel 20261017-171446, 3 expansions).
			// Step to a nearby point in a straight line from which the coarse grid does route.
			@route = RouteFromPocket(pos, it.approach, start);
			it.escaped = route !is null;
		}
		it.partial = false;
		if ((route is null || route.length() == 0) && it.partialHops < PARTIAL_HOPS)
		{
			// no route now (the floor is cut where the player stands: pilot-crosslevel
			// 20261017-172902, spawn -> exit no longer routed after fights, though nav-drift
			// 20261017-173940 found the same layout's answers steady when idle or culled):
			// go to the reached point nearest the exit and route again from there
			@route = NavRoute(start, it.approach, true);
			it.partial = route !is null && route.length() > 0;
		}
		if (route is null || route.length() == 0)
			return false;
		if (it.escaped)
			route.insertAt(0, start);
		@it.path = route;
		it.wp = 0;
		it.goal = it.partial ? route[route.length() - 1] : it.approach;
		if (it.partial)
			it.partialHops++;
		return true;
	}

	// steer along the path; true when within tol of the goal. As the game's own PathFollower
	// (Behaviors/Actors/Enemies/Movements/PathFollower.as:83-127): a node is passed once the
	// player projects past it onto the next leg, and a player that did not move since the last
	// frame slides 45 degrees toward whichever side a short raycast finds free.
	bool FollowPath(PilotIntent@ it, vec2 pos, vec2 &out move)
	{
		move = vec2();
		if (dist(pos, it.goal) <= it.tol)
			return true;
		while (it.path !is null && it.wp < it.path.length() && dist(pos, it.path[it.wp]) < 8.0f)
			it.wp++;
		if (it.path !is null && it.wp + 1 < it.path.length())
		{
			vec2 a = it.path[it.wp] - it.path[it.wp + 1];
			float dt = dot(a, pos - it.path[it.wp + 1]) * 0.95f;
			if (dt > 0 && dt < lengthsq(a))
				it.wp++;
		}
		vec2 to = (it.path !is null && it.wp < it.path.length()) ? it.path[it.wp] : it.goal;
		vec2 dir = to - pos;
		if (length(dir) < 0.01f)
			return false;
		move = normalize(dir);
		if (distsq(it.lastPos, pos) <= 0.1f)
		{
			float ang = atan(dir.y, dir.x);
			float da = 3.14159265f / 4;
			vec2 d1(cos(ang + da), sin(ang + da));
			vec2 d2(cos(ang - da), sin(ang - da));
			bool b1 = g_scene.RaycastQuick(pos, pos + d1 * SLIDE_PROBE, ~0, RaycastType::Any);
			bool b2 = g_scene.RaycastQuick(pos, pos + d2 * SLIDE_PROBE, ~0, RaycastType::Any);
			if (b1 != b2)
				move = b1 ? d2 : d1;
		}
		it.lastPos = pos;
		return false;
	}

	// a direction the player can step in: of 16, the one nearest `want` whose short raycast
	// hits nothing; vec2() when every one is blocked
	vec2 FreeDir(vec2 pos, vec2 want)
	{
		float base = atan(want.y, want.x);
		for (int k = 0; k < 16; k++)
		{
			float a = base + ((k % 2 == 0) ? 1 : -1) * ((k + 1) / 2) * 3.14159265f / 8;
			vec2 d(cos(a), sin(a));
			if (!g_scene.RaycastQuick(pos, pos + d * WIGGLE_PROBE, ~0, RaycastType::Any))
				return d;
		}
		return vec2();
	}

	bool TightWrite(PilotIntent@ it, GameInput& gi, vec2 move)
	{
		string why = TightOwnerReason(it, gi, "pre_write", move);
		if (why != "") { it.tightForeign = true; PilotEnd("interrupted", why); return false; }
		WriteInput(gi, move, false, vec2(), null, false); // the existing owned writer only
		it.tightWrites = g_inputFrames;
		it.tightExpectedMove = move;
		TightProbeReadback(it, gi, move);
		return true;
	}

	// NEW endpoint corrections only: stricter than qa_routeleg.complete (12px).
	// Initial/approach routes keep their old acceptance, including longer routes.
	// A correction accepts no partial/escape-start/implicit straight final segment.
	bool TightRouteBound(PilotIntent@ it, vec2 from)
	{
		if (it.goal.x != it.tightGoal.x || it.goal.y != it.tightGoal.y || it.path is null
			|| it.path.length() == 0 || it.path.length() > 256 || dist(from, it.path[0]) > it.tightTol)
			return false;
		float arc = 0;
		vec2 previous = from;
		for (uint i = 0; i < it.path.length(); i++)
		{
			vec2 point = it.path[i];
			if (!ArrivalFinite(point.x) || !ArrivalFinite(point.y)) return false;
			arc += dist(previous, point);
			if (!ArrivalFinite(arc) || arc > 128.0f) return false;
			previous = point;
		}
		return dist(previous, it.tightGoal) <= it.tightTol;
	}

	bool TightRepath(PilotIntent@ it, vec2 pos, bool endpointCorrection)
	{
		if (it.tightCorrections >= 4) { PilotEnd("failed", "tight correction budget"); return false; }
		it.tightCorrections++;
		// Preserve the original goal. Only a NEW settled-endpoint correction also
		// needs a complete bounded local polyline; approach retries keep old routing.
		bool routed = Repath(it, pos);
		if (!routed || it.goal.x != it.tightGoal.x || it.goal.y != it.tightGoal.y
			|| (endpointCorrection && !TightRouteBound(it, pos)))
		{ PilotEnd("no_route", "tight correction requires original goal"); return false; }
		it.tightHolding = false; it.tightQuiet = 0; it.tightInsideQuiet = 0; it.tightNeutral = 0;
		it.tightPulseCredit = 0; // fresh actual-origin route; no old pulse debt
		it.stuckFrom = pos; it.stuckMs = 0;
		return true;
	}

	// Bounded input-only arrival. Scene observations are not engine phase clocks;
	// zero raw velocity is unit independent. No gain estimate from the last stick.
	void TightFrame(PilotIntent@ it, int ms, GameInput& gi, vec2 pos)
	{
		int now = int(g_scene.GetTime());
		if (ms <= 0 || ms > 250 || now < 0 || now <= it.tightNow
			|| !ArrivalFinite(pos.x) || !ArrivalFinite(pos.y)
			|| it.goal.x != it.tightGoal.x || it.goal.y != it.tightGoal.y || it.tol != it.tightTol)
		{ PilotEnd("failed", "tight stale/nonfinite observation or changed goal/bound"); return; }
		it.tightObservations++;
		auto actor = GetLocalPlayer();
		auto body = actor.m_unit.GetPhysicsBody();
		if (body is null) { PilotEnd("failed", "tight body unavailable"); return; }
		vec2 velocity = body.GetLinearVelocity(); // no setter, scale or velocity conversion
		if (!ArrivalFinite(velocity.x) || !ArrivalFinite(velocity.y))
		{ PilotEnd("failed", "tight nonfinite body velocity"); return; }
		float step = dist(pos, it.tightPrevious);
		if (!ArrivalFinite(step)) { PilotEnd("failed", "tight nonfinite world step"); return; }
		it.tightStepPeak = max(it.tightStepPeak, step);
		it.tightPrevious = pos; it.tightNow = now;
		float remaining = dist(pos, it.tightGoal);
		if (remaining <= it.tightTol) it.tightHolding = true;
		if (it.tightHolding)
		{
			it.tightPulseCredit = 0; // settlement cannot accumulate or discharge a pulse
			if (++it.tightHolds > 12) { PilotEnd("failed", "tight hold observation budget"); return; }
			bool neutral = it.tightExpectedMove.x == 0 && it.tightExpectedMove.y == 0;
			bool quiet = neutral && step <= 0.05f && velocity.x == 0 && velocity.y == 0;
			it.tightQuiet = quiet ? it.tightQuiet + 1 : 0;
			it.tightInsideQuiet = quiet && remaining <= it.tightTol ? it.tightInsideQuiet + 1 : 0;
			if (it.tightNeutral >= 4 && it.tightQuiet >= 2
				&& (remaining > it.tightTol || it.tightInsideQuiet >= 2))
			{
				if (remaining <= it.tightTol)
				{
					if (TightOwnerReason(it, gi, "final_release") != "")
					{ it.tightForeign = true; PilotEnd("interrupted", "tight final owner changed"); return; }
					// Retain the original diagnostic and owned completion release sequence.
					try { BeginArrivalProbe(it, gi); } catch { g_arrivalId = ""; g_arrivalTail = 0; }
					ReleaseInput(gi);
					it.tightWrites = g_inputFrames; it.tightExpectedMove = vec2();
					try { AfterArrivalProbe(gi); } catch { g_arrivalId = ""; g_arrivalTail = 0; }
					PilotEnd("done", "arrived neutral and settled"); return;
				}
				// Correct only after actual neutral settling, from the actual new point.
				if (!TightRepath(it, pos, true)) return;
			}
			else
			{
				if (TightWrite(it, gi, vec2())) it.tightNeutral++;
				return;
			}
		}

		// This branch replaces generic stuck detection only for tight arrivals.
		// Every automatic retry consumes the same cumulative correction budget.
		it.stuckMs += ms;
		if (it.stuckMs >= 1000)
		{
			if (dist(pos, it.stuckFrom) < 3 && !TightRepath(it, pos, false)) return;
			it.stuckFrom = pos; it.stuckMs = 0;
		}
		vec2 move;
		if (FollowPath(it, pos, move) || !ArrivalFinite(move.x) || !ArrivalFinite(move.y) || length(move) <= 0)
		{ PilotEnd("failed", "tight route has no valid outside-band direction"); return; }
		// Observed displacement is a conservative bound, NOT a stick/velocity gain.
		// Unknown/zero motion uses a bounded small pulse and never grants done.
		if (remaining <= max(16.0f, 4 * it.tightStepPeak))
		{
			float cap = it.tightStepPeak > 0 ? remaining / (4 * max(it.tightTol, it.tightStepPeak)) : 0.125f;
			it.tightCap = min(it.tightCap, min(1.0f, cap));
		}
		if (step <= 0.0001f && (it.tightExpectedMove.x != 0 || it.tightExpectedMove.y != 0)) it.tightNoMotion++;
		else it.tightNoMotion = 0;
		if (it.tightNoMotion > 8) { PilotEnd("failed", "tight no observed movement"); return; }
		// Do not rely on subunit stick magnitude surviving to the next callback.
		// Cap is a duty ratio over these observations, NOT a native frame/physics rate.
		if (!ArrivalFinite(it.tightCap) || it.tightCap <= 0 || it.tightCap > 1
			|| !ArrivalFinite(it.tightPulseCredit) || it.tightPulseCredit < 0 || it.tightPulseCredit >= 1)
		{ PilotEnd("failed", "tight invalid pulse duty or credit"); return; }
		vec2 command = move;
		if (it.tightCap == 1) it.tightPulseCredit = 0;
		else
		{
			it.tightPulseCredit += it.tightCap;
			command = vec2();
			if (it.tightPulseCredit >= 1) { it.tightPulseCredit -= 1; command = move; }
		}
		TightWrite(it, gi, command); // original guarded owned writer/tracker only
	}

	string CheckInterrupts(PilotIntent@ it, PlayerRecord@ rec)
	{
		for (uint i = 0; i < it.until.length(); i++)
		{
			string u = it.until[i];
			if (u == "dead" && rec.IsDead())
				return u;
			if (u == "hp_below" && it.hpBelow >= 0 && rec.CurrentHealth() * 100.0f < it.hpBelow * rec.MaxHealth())
				return u + ":" + it.hpBelow;
			if (u == "under_attack" && it.prevHp >= 0 && rec.CurrentHealth() < it.prevHp)
				return u;
			if (u == "target_dead" && it.target.IsValid() && TargetGone(it.target))
				return u;
			if (u == "menu_open" && TopWindow() != "")
				return u + ":" + TopWindow();
		}
		return "";
	}

	// ---- reflexes: standing orders the engine runs every frame ----------------
	// A bot reacts through the gl channel, and one round trip (console line + log flush) took
	// 1.7 s in which a swarm took 140 hp off an unsteered player (pilot-crosslevel
	// 20261017-161022). Reflexes close that gap: set once (`pilot reflex`), they run inside
	// every intent and between intents. Off by default.
	float g_reflexPotion = -1;     // drink when hp% < this (and a charge is left)
	float g_reflexFire = 0;        // aim at and fire on the nearest enemy within this radius
	int g_reflexPotionSince = 100000;
	int g_reflexFireSince = 100000;
	int g_reflexPotions = 0;

	class ReflexOut
	{
		bool aimSet = false;
		vec2 aim;
		array<string> buttons;
		bool pressed = false;
	}

	// adds the reflexes' buttons and aim to o; true if any acted
	bool Reflexes(int ms, vec2 pos, PlayerRecord@ rec, const string &in kind, ReflexOut@ o)
	{
		bool acted = false;
		g_reflexPotionSince += ms;
		g_reflexFireSince += ms;
		if (g_reflexPotion > 0 && kind != "potion" && g_reflexPotionSince > 1200
			&& rec.CurrentHealth() * 100.0f < g_reflexPotion * rec.MaxHealth()
			&& rec.potionChargesUsed < rec.currStats.PotionCharges)
		{
			o.buttons.insertLast("potion");
			o.pressed = true;
			g_reflexPotionSince = 0;
			g_reflexPotions++;
			Json j;
			Emit(j.Str("ev", "reflex").Str("what", "potion").Int("hp", rec.CurrentHealth())
				.Int("hpMax", rec.MaxHealth()).Int("used", rec.potionChargesUsed).Int("tick", g_tick));
			acted = true;
		}
		if (g_reflexFire > 0 && !o.aimSet)
		{
			UnitPtr foe = NearestEnemy(pos, int(g_reflexFire));
			if (!TargetGone(foe))
			{
				vec2 d = xy(foe.GetPosition()) - pos;
				o.aimSet = true;
				o.aim = length(d) > 0.01f ? normalize(d) : vec2(1, 0);
				o.buttons.insertLast("main");
				if (g_reflexFireSince > 250)
				{
					o.pressed = true;
					g_reflexFireSince = 0;
				}
				acted = true;
			}
		}
		return acted;
	}

	void PilotFrame(int ms, GameInput& gi)
	{
		auto it = g_intent;
		if (it is null)
		{
			// between intents: only the reflexes steer, standing still
			auto rrec = GetLocalPlayerRecord();
			auto rplr = GetLocalPlayer();
			if (!g_pilotPaused && rrec !is null && rplr !is null && !rrec.IsDead()
				&& (g_reflexPotion > 0 || g_reflexFire > 0))
			{
				ReflexOut o;
				if (Reflexes(ms, xy(rplr.m_unit.GetPosition()), rrec, "", o))
				{
					WriteInput(gi, vec2(), o.aimSet, o.aim, o.buttons, o.pressed);
					g_releasePending = true;
					return;
				}
			}
			if (Releasing())
				ReleaseInput(gi);
			return;
		}
		// Check before pause/record early returns: they otherwise write a neutral or
		// retain an old tight state after a foreign takeover or actor replacement.
		if (it.tight)
		{
			it.tightDiagEntries++; // independent of the later intent tick/frame counters
			string ownerWhy = TightOwnerReason(it, gi, "frame_entry");
			if (ownerWhy != "") { it.tightForeign = true; PilotEnd("interrupted", ownerWhy); return; }
			if (g_pilotPaused) { PilotEnd("interrupted", "tight paused"); return; }
		}
		if (g_pilotPaused)
		{
			if (g_pilotSteps <= 0)
			{
				ReleaseInput(gi);      // paused = hands off the controller
				return;
			}
			g_pilotSteps--;
		}
		auto rec = GetLocalPlayerRecord();
		auto plr = GetLocalPlayer();
		if (rec is null)
			return;
		g_tick++;
		it.frames++;
		it.elapsed += ms;

		string why = CheckInterrupts(it, rec);
		it.prevHp = rec.CurrentHealth();
		if (why != "")
		{
			PilotEnd("interrupted", why);
			return;
		}
		if (rec.IsDead() || plr is null)
		{
			PilotEnd("failed", "player dead or not spawned");
			return;
		}
		if (it.elapsed > it.timeoutMs)
		{
			PilotEnd("timeout", "after " + it.timeoutMs + " ms");
			return;
		}

		vec2 pos = xy(plr.m_unit.GetPosition());
		if (it.tight) { TightFrame(it, ms, gi, pos); return; }
		vec2 move;
		bool aimSet = false;
		vec2 aim;
		array<string> buttons;
		bool pressed = false;

		// stuck detection for the moving intents: under 3 units in a second -> repath (3x) then fail
		it.stuckMs += ms;
		if (it.stuckMs >= 1000)
		{
			bool fighting = it.kind == "attack" || it.kind == "kite";
			bool moving = it.kind == "path_to" || it.kind == "exit" || it.kind == "move" || (fighting && it.approaching)
				|| (it.kind == "use" && it.approaching);
			if (moving && dist(pos, it.stuckFrom) < 3.0f && dist(pos, it.goal) > it.tol)
			{
				it.repaths++;
				bool rerouted = it.kind == "move" || it.pushing || fighting
					|| (it.kind == "exit" ? RouteExit(it, pos) : Repath(it, pos));
				if (!rerouted && it.kind == "exit")
				{
					// wedged so that no Pathfind leaves this spot (pilot-crosslevel
					// 20261017-164137: NavRoute expanded only its start): step out, then route
					it.wiggleDir = FreeDir(pos, it.anchor - pos);
					if (length(it.wiggleDir) > 0)
					{
						it.wiggleMs = WIGGLE_MS;
						rerouted = true;
					}
				}
				if (fighting && it.repaths > 3)
				{
					// cannot close in on this one (both sides wedged in trees: pilot-consumables
					// 20261017-163601): "nearest" moves on to the next, a named target fails
					if (!it.nearest)
					{
						PilotEnd("failed", "target " + it.target.GetId() + " unreachable (stuck at " + int(pos.x) + "," + int(pos.y) + ")");
						return;
					}
					it.skip.insertLast(it.target.GetId());
					it.target = NearestEnemy(pos, ENGAGE, it.skip);
					@it.path = null;
					it.repaths = 0;
					if (TargetGone(it.target))
					{
						PilotEnd("failed", "no reachable enemy within " + ENGAGE + " (" + it.skip.length() + " unreachable)");
						return;
					}
				}
				else if (it.repaths > 3 || !rerouted)
				{
					PilotEnd("failed", "stuck at " + int(pos.x) + "," + int(pos.y));
					return;
				}
				else if (fighting)
					@it.path = null;   // re-plan the approach next frame
			}
			it.stuckFrom = pos;
			it.stuckMs = 0;
		}

		if (it.kind == "wait")
		{
			if (it.elapsed >= it.range)
			{
				PilotEnd("done", "waited");
				return;
			}
		}
		else if (it.kind == "move")
		{
			if (dist(pos, it.goal) <= it.tol)
			{
				PilotEnd("done", "arrived");
				return;
			}
			move = normalize(it.goal - pos);
		}
		else if (it.kind == "path_to")
		{
			if (FollowPath(it, pos, move))
			{
				// Do not leave the previous move live until the pending release.
				// PilotEnd still schedules its normal neutral tail after this write.
				try { BeginArrivalProbe(it, gi); }
				catch { g_arrivalId = ""; g_arrivalTail = 0; }
				ReleaseInput(gi);
				try { AfterArrivalProbe(gi); }
				catch { g_arrivalId = ""; g_arrivalTail = 0; }
				PilotEnd("done", "arrived");
				return;
			}
		}
		else if (it.kind == "exit")
		{
			// walk into the exit's area, then Use it; the level load ends this script module,
			// so "done" is the client seeing the next level's boot
			if (it.wiggleMs > 0)
			{
				move = it.wiggleDir;
				it.wiggleMs -= ms;
				if (it.wiggleMs <= 0 && !RouteExit(it, pos))
				{
					PilotEnd("no_route", "no route to the exit at " + int(it.anchor.x) + "," + int(it.anchor.y)
						+ " after stepping out of a wedge (NavRoute: " + it.navExpanded + " grid expansions)");
					return;
				}
			}
			else if (it.pushing || InExitArea(it.exitWs, plr.m_unit))
			{
				it.pushing = true;
				move = (dist(pos, it.anchor) > 6.0f && !InExitArea(it.exitWs, plr.m_unit)) ? normalize(it.anchor - pos) : vec2();
			}
			else if (FollowPath(it, pos, move) && it.partial)
			{
				if (!RouteExit(it, pos))
				{
					PilotEnd("no_route", "no route to the exit at " + int(it.anchor.x) + "," + int(it.anchor.y)
						+ " after " + it.partialHops + " partial routes (NavRoute: " + it.navExpanded + " grid expansions)");
					return;
				}
				it.stuckMs = 0;
				it.stuckFrom = pos;
			}
			else if (dist(pos, it.goal) <= it.tol)
			{
				it.pushing = true;     // at the approach point: walk straight into the exit's area
				it.stuckMs = 0;
				it.stuckFrom = pos;
			}
			it.sincePulse += ms;
			auto top = plr.GetTopUsable();
			if (top !is null && cast<WorldScript::LevelExitAreaNext>(top) !is null && it.sincePulse > 500)
			{
				buttons.insertLast("use");
				pressed = true;
				it.sincePulse = 0;
				it.pulses++;
			}
		}
		else if (it.kind == "attack" || it.kind == "kite")
		{
			if (it.nearest && TargetGone(it.target))
				it.target = NearestEnemy(pos, ENGAGE, it.skip);
			if (TargetGone(it.target))
			{
				PilotEnd("done", it.nearest ? "no live enemy within " + ENGAGE : "target dead");
				return;
			}
			vec2 tp = xy(it.target.GetPosition());
			float d = dist(pos, tp);
			vec2 to = d > 0.01f ? normalize(tp - pos) : vec2(1, 0);
			aimSet = true;
			aim = to;
			float closeIn = it.kind == "attack" ? MELEE_RANGE : it.range * 1.2f;
			if (d > closeIn)
			{
				// closing in walks the engine path (a beeline sticks on walls), re-planned as it moves
				it.sincePath += ms;
				if (it.path is null || it.sincePath > 600)
				{
					it.goal = tp;
					if (!Repath(it, pos))
						RouteNear(it, pos, tp);
					it.sincePath = 0;
				}
				FollowPath(it, pos, move);
				it.approaching = true;
			}
			else if (it.kind == "attack")
			{
				move = vec2(0, 0);
				it.approaching = false;
			}
			else if (d < it.range * 0.8f)
			{
				it.approaching = false;
				// back away from the pack, not just the target (a swarm closes from all sides)
				auto foes = g_scene.FetchActorsWithOtherTeam(g_team_player, pos, ENGAGE);
				vec2 c;
				int n = 0;
				for (uint i = 0; i < foes.length(); i++)
				{
					if (TargetGone(foes[i]))
						continue;
					c += xy(foes[i].GetPosition());
					n++;
				}
				vec2 away = n > 0 ? pos - c / float(n) : pos - tp;
				move = length(away) > 0.01f ? normalize(away) : to * -1.0f;
				// dash out when something is in melee reach
				it.sinceDash += ms;
				if (d < MELEE_RANGE * 1.5f && it.sinceDash > 1500)
				{
					buttons.insertLast("dash");
					pressed = true;
					it.sinceDash = 0;
				}
			}
			else
			{
				move = vec2(-to.y, to.x);       // strafe around the target at range
				it.approaching = false;
			}
			// kite fires at anything within ENGAGE: closing in can stall on a wall while the
			// target waits behind it (pilot-consumables 20261017-163406: 60 s at 92 units)
			if (d <= max(it.range, MELEE_RANGE) * 1.3f || (it.kind == "kite" && d <= ENGAGE))
			{
				buttons.insertLast("main");
				it.sincePulse += ms;
				if (it.sincePulse > 250)
				{
					pressed = true;
					it.sincePulse = 0;
				}
			}
		}
		else if (it.kind == "use")
		{
			// a solid target (a chest) stops the player short of tol from its centre: it is
			// in reach once it is the player's top usable
			auto reach = plr.GetTopUsable();
			bool inReach = reach !is null && it.target.IsValid() && reach.GetUseUnit() == it.target;
			it.approaching = it.target.IsValid() && !it.target.IsDestroyed() && !inReach
				&& dist(pos, xy(it.target.GetPosition())) > it.tol;
			if (it.approaching)
			{
				if (FollowPath(it, pos, move))
					move = vec2();
			}
			else
			{
				auto top = plr.GetTopUsable();
				bool targetUsable = top !is null && (!it.target.IsValid() || top.GetUseUnit() == it.target) && top.CanUse(plr);
				if (it.pulses > 0 && (!targetUsable || (it.target.IsValid() && it.target.IsDestroyed())))
				{
					PilotEnd("done", "used (no longer usable)");
					return;
				}
				it.sincePulse += ms;
				if (it.sincePulse > 400)
				{
					if (!targetUsable)
					{
						PilotEnd("failed", top is null ? "nothing usable here" : "top usable is not the target");
						return;
					}
					if (it.pulses >= 4)
					{
						PilotEnd("failed", "still usable after 4 presses");
						return;
					}
					buttons.insertLast("use");
					pressed = true;
					it.sincePulse = 0;
					it.pulses++;
				}
			}
		}
		else if (it.kind == "potion")
		{
			if (it.pulses == 0)
			{
				buttons.insertLast("potion");
				pressed = true;
				it.pulses++;
				it.potionsUsed0 = rec.potionChargesUsed;
			}
			else if (rec.potionChargesUsed > it.potionsUsed0)
			{
				PilotEnd("done", "drank (charges used " + rec.potionChargesUsed + ")");
				return;
			}
			else if (it.elapsed > 1000)
			{
				PilotEnd("failed", "no charge used (charges " + rec.currStats.PotionCharges + ", used " + rec.potionChargesUsed + ")");
				return;
			}
		}

		ReflexOut ro;
		ro.aimSet = aimSet;
		ro.aim = aim;
		ro.pressed = pressed;
		ro.buttons = buttons;
		Reflexes(ms, pos, rec, it.kind, ro);
		aimSet = ro.aimSet;
		aim = ro.aim;
		pressed = ro.pressed;
		buttons = ro.buttons;
		WriteInput(gi, move, aimSet, aim, buttons, pressed);

		if (it.frames % PTICK_EVERY == 1)
		{
			Json j;
			j.Str("ev", "ptick").Int("tick", g_tick).Str("id", it.id).Str("intent", it.kind)
				.Num("x", pos.x).Num("y", pos.y).Int("hp", rec.CurrentHealth()).Int("hpMax", rec.MaxHealth())
				.Num("mx", move.x).Num("my", move.y).Int("wp", it.wp).Int("pathLen", it.path is null ? 0 : it.path.length());
			if (it.target.IsValid())
				j.Int("target", it.target.GetId()).Num("dist", dist(pos, xy(it.target.GetPosition())));
			if (it.kind == "exit")
				j.Bool("nav", it.nav).Bool("partial", it.partial).Bool("pushing", it.pushing)
					.Num("gx", it.goal.x).Num("gy", it.goal.y);
			Emit(j);
		}
	}

	// ---- verbs ---------------------------------------------------------------

	UnitPtr UnitArg(const string &in s, vec2 from, bool &out nearest)
	{
		nearest = s == "nearest";
		if (nearest)
			return NearestEnemy(from, 400);
		return g_scene.GetUnit(int(parseInt(s)));
	}

	void PilotStatus(const string &in id)
	{
		auto j = Reply(id, true);
		j.Bool("paused", g_pilotPaused).Int("tick", g_tick).Num("reflexPotion", g_reflexPotion)
			.Num("reflexFire", g_reflexFire).Int("reflexPotions", g_reflexPotions);
		auto plr = GetLocalPlayer();
		if (plr !is null)
			j.Num("x", plr.m_unit.GetPosition().x).Num("y", plr.m_unit.GetPosition().y);
		if (g_intent !is null)
			j.Str("intent", g_intent.kind).Str("intentId", g_intent.id).Int("ms", g_intent.elapsed)
				.Int("target", g_intent.target.IsValid() ? g_intent.target.GetId() : 0);
		else
			j.Str("intent", "");
		Emit(j);
	}

	string TightAdmit(PilotIntent@ it, vec2 pos)
	{
		if (g_intent !is null || g_pilotPaused || Releasing() || g_scene is null
			|| g_inputs.length() == 0 || g_inputs.length() > MAX_INPUTS
			|| !ArrivalFinite(it.goal.x) || !ArrivalFinite(it.goal.y)
			|| !ArrivalFinite(pos.x) || !ArrivalFinite(pos.y) || it.timeoutMs <= 0)
			return "tight admission needs idle, unpaused, finite owned context";
		auto actor = GetLocalPlayer();
		auto rec = GetLocalPlayerRecord();
		if (actor is null || rec is null || rec.IsDead() || actor.IsDead() || !actor.m_unit.IsValid())
			return "tight admission needs live actor";
		it.tight = true; it.tightGoal = it.goal; it.tightTol = it.tol;
		it.tightPlayer = actor.m_unit.GetId(); it.tightBoots = g_boots;
		it.tightLevel = GetCurrentLevelFilename();
		@it.tightScene = g_scene; @it.tightRecord = rec; @it.tightActor = actor;
		it.tightInputs = g_inputs;
		for (uint i = 0; i < g_inputs.length(); i++)
		{
			if (g_inputs[i] is null) return "tight admission null input";
			it.tightPads.insertLast(g_inputs[i].UsingGamepad);
		}
		it.tightWrites = g_inputFrames; it.tightPrevious = pos;
		it.tightNow = int(g_scene.GetTime());
		if (it.tightLevel.isEmpty() || it.tightNow < 0) return "tight admission missing world/clock";
		return TightOwnerReason(it, GetInput(), "admit"); // neutral expected move, no new registration
	}

	// pilot <intent|pause|resume|step|target|stop|status|reflex> [args] [until=..] [timeout=ms]:
	// start an intent (path_to, move, exit, attack, kite, use, potion, wait) that runs in-engine
	// until done or an `until` interrupt, ending in a "pilot" event; or control the running one;
	// `reflex potion=<hp%> fire=<radius>` sets standing orders. Python client: gamelab/pilot.py.
	void VerbPilot(const string &in id, array<string>@ argsIn)
	{
		string sub = argsIn.length() > 0 ? argsIn[0] : "status";
		// positional args and key=value options
		array<string> args;
		string untilArg = "";
		int timeoutMs = 30000;
		for (uint i = 1; i < argsIn.length(); i++)
		{
			if (argsIn[i].findFirst("until=") == 0)
				untilArg = argsIn[i].substr(6);
			else if (argsIn[i].findFirst("timeout=") == 0)
				timeoutMs = int(parseInt(argsIn[i].substr(8)));
			else
				args.insertLast(argsIn[i]);
		}

		if (sub == "status")
		{
			PilotStatus(id);
			return;
		}
		if (sub == "pause" || sub == "resume")
		{
			g_pilotPaused = sub == "pause";
			g_pilotSteps = 0;
			PilotStatus(id);
			return;
		}
		if (sub == "reflex")
		{
			// reflex [potion=<hp%>|off] [fire=<radius>|off]
			for (uint i = 0; i < args.length(); i++)
			{
				auto kv = args[i].split("=");
				float v = kv.length() > 1 && kv[1] != "off" ? parseFloat(kv[1]) : 0;
				if (kv[0] == "potion" && kv.length() > 1)
					g_reflexPotion = v > 0 ? v : -1;
				else if (kv[0] == "fire" && kv.length() > 1)
					g_reflexFire = v;
				else
				{
					Fail(id, "unknown reflex '" + args[i] + "': potion=<hp%>|off, fire=<radius>|off");
					return;
				}
			}
			PilotStatus(id);
			return;
		}
		if (sub == "step")
		{
			g_pilotPaused = true;
			g_pilotSteps = args.length() > 0 ? int(parseInt(args[0])) : 1;
			PilotStatus(id);
			return;
		}
		if (sub == "stop")
		{
			bool had = g_intent !is null;
			PilotEnd("interrupted", "stop");
			Emit(Reply(id, true).Bool("stopped", had));
			return;
		}
		if (sub == "target")
		{
			if (g_intent is null || (g_intent.kind != "attack" && g_intent.kind != "kite"))
			{
				Fail(id, "no attack/kite intent to retarget");
				return;
			}
			UnitPtr u = args.length() > 0 ? g_scene.GetUnit(int(parseInt(args[0]))) : UnitPtr();
			if (TargetGone(u))
			{
				Fail(id, "unit is not a live actor");
				return;
			}
			g_intent.target = u;
			g_intent.nearest = false;
			Emit(Reply(id, true).Int("target", u.GetId()));
			return;
		}

		if (INTENTS.find(sub) < 0)
		{
			Fail(id, "unknown pilot verb '" + sub + "' (intents: " + join(INTENTS, ",") + "; control: pause,resume,step,target,stop,status)");
			return;
		}
		// Do not replace a live tight controller and leave its release tail under a
		// different intent. Explicit stop + completed neutral tail precedes admission.
		if (g_intent !is null && g_intent.tight)
		{ Fail(id, "tight arrival active; stop and observe release before another intent"); return; }
		auto plr = GetLocalPlayer();
		if (plr is null)
		{
			Fail(id, "no spawned local player");
			return;
		}
		vec2 pos = xy(plr.m_unit.GetPosition());

		PilotIntent it;
		it.id = id;
		it.kind = sub;
		it.timeoutMs = timeoutMs;
		it.stuckFrom = pos;
		if (untilArg != "")
		{
			auto parts = untilArg.split(",");
			for (uint i = 0; i < parts.length(); i++)
			{
				auto kv = parts[i].split(":");
				if (INTERRUPTS.find(kv[0]) < 0)
				{
					Fail(id, "unknown interrupt '" + kv[0] + "' (closed vocabulary: " + join(INTERRUPTS, ",") + ")");
					return;
				}
				if (kv[0] == "hp_below")
					it.hpBelow = kv.length() > 1 ? parseFloat(kv[1]) : 50.0f;
				it.until.insertLast(kv[0]);
			}
		}

		string err = "";
		if (sub == "move" || sub == "path_to")
		{
			if (args.length() < 2)
				err = "usage: pilot " + sub + " x y [tol]";
			else
			{
				it.goal = vec2(parseFloat(args[0]), parseFloat(args[1]));
				if (args.length() > 2)
					it.tol = parseFloat(args[2]);
			}
		}
		else if (sub == "attack" || sub == "kite")
		{
			it.target = UnitArg(args.length() > 0 ? args[0] : "nearest", pos, it.nearest);
			if (!TargetGone(it.target))
				it.goal = xy(it.target.GetPosition());
			it.range = sub == "kite" ? (args.length() > 1 ? parseFloat(args[1]) : 70.0f) : MELEE_RANGE;
			if (TargetGone(it.target))
				err = "no live target";
		}
		else if (sub == "use")
		{
			it.tol = 14.0f;
			if (args.length() > 0)
			{
				bool unused;
				it.target = UnitArg(args[0], pos, unused);
				if (!it.target.IsValid())
					err = "no unit " + args[0];
				else
					it.goal = xy(it.target.GetPosition());
			}
		}
		else if (sub == "wait")
			it.range = args.length() > 0 ? parseFloat(args[0]) : 1000.0f;
		else if (sub == "exit")
		{
			auto ws = NearestExit(pos);
			if (ws is null)
			{
				if (g_intent !is null)
					PilotEnd("interrupted", "replaced by " + id);
				Emit(Reply(id, true).Str("accepted", sub));
				@g_intent = it;
				PilotEnd("no_route", "no enabled level exit in this level");
				return;
			}
			@it.exitWs = ws;
			it.anchor = ExitStandPoint(ws, it.areaFound);
			it.goal = it.anchor;
			it.tol = 6.0f;
		}
		if (err != "")
		{
			Fail(id, err);
			return;
		}

		if (sub == "path_to" && ArrivalFinite(it.tol) && it.tol > 0 && it.tol <= 2)
		{
			string admission = TightAdmit(it, pos);
			if (admission != "") { Fail(id, admission); return; }
		}

		// a new intent replaces the running one (tight admission requires idle)
		if (g_intent !is null)
			PilotEnd("interrupted", "replaced by " + id);
		auto reply = Reply(id, true).Str("accepted", sub).Int("tick", g_tick);
		bool routed = true;
		if (sub == "path_to" || sub == "exit" || (sub == "use" && it.target.IsValid()))
		{
			routed = sub == "exit" ? RouteExit(it, pos) : Repath(it, pos);
			if (sub == "exit")
				reply.Num("ux", it.exitWs.GetUnit().GetPosition().x).Num("uy", it.exitWs.GetUnit().GetPosition().y)
					.Bool("area", it.areaFound).Num("ax", it.anchor.x).Num("ay", it.anchor.y).Bool("nav", it.nav).Int("navExpanded", it.navExpanded).Bool("escaped", it.escaped).Bool("partial", it.partial)
					.Num("apx", it.approach.x).Num("apy", it.approach.y);
			reply.Int("pathLen", it.path is null ? 0 : it.path.length()).Num("gx", it.goal.x).Num("gy", it.goal.y);
		}
		if (it.target.IsValid())
			reply.Int("target", it.target.GetId());
		if (it.tight)
		{
			string ownerWhy = TightOwnerReason(it, GetInput(), "admit_after_route");
			if (ownerWhy != "" || it.goal.x != it.tightGoal.x || it.goal.y != it.tightGoal.y)
			{ Fail(id, "tight initial route changed goal or ownership: " + ownerWhy); return; }
			reply.Bool("tight", true).Int("maxCorrections", 4).Int("maxHoldObservations", 12);
		}
		Emit(reply);
		@g_intent = it;
		if (!routed)
			PilotEnd("no_route", "engine pathfinder found no path to " + int(it.goal.x) + "," + int(it.goal.y)
				+ (sub == "exit" ? " (NavRoute: none within " + it.navExpanded + " grid expansions)" : ""));
	}

	// where the player is, as a travel-graph node: "town", or "<missionId>/<floorId>"
	// (every generated floor is levels/generated.lvl, so the level file cannot be the key)
	string Place()
	{
		if (g_inTown)
			return "town";
		auto def = MissionManager::GetCurrentMission();
		if (def is null)
			return GetCurrentLevelFilename();
		uint i = MissionManager::g_module.m_missionLevelIndex;
		return def.m_id + "/" + (i < def.m_levels.length() ? def.m_levels[i].m_id : ("" + i));
	}

	// pathfind x y [diameter] [maxDistance] [maxRange]: the engine pathfinder's answer from the
	// player, read-only (nodes, length, first and last node)
	void VerbPathfind(const string &in id, array<string>@ args)
	{
		auto plr = GetLocalPlayer();
		if (plr is null || args.length() < 2)
		{
			Fail(id, plr is null ? "no spawned local player" : "usage: pathfind x y [diameter] [maxDistance] [maxRange] [fromX fromY]");
			return;
		}
		vec2 from = xy(plr.m_unit.GetPosition());
		vec2 to(parseFloat(args[0]), parseFloat(args[1]));
		int diameter = args.length() > 2 ? int(parseInt(args[2])) : PATH_DIAMETER;
		float maxDistance = args.length() > 3 ? parseFloat(args[3]) : -1.0f;
		float maxRange = args.length() > 4 ? parseFloat(args[4]) : -1.0f;
		if (args.length() > 6)
			from = vec2(parseFloat(args[5]), parseFloat(args[6]));
		auto path = g_scene.Pathfind(from, to, diameter, maxDistance, maxRange);
		auto j = Reply(id, true).Num("fx", from.x).Num("fy", from.y).Num("tx", to.x).Num("ty", to.y)
			.Num("straight", dist(from, to)).Int("nodes", path is null ? -1 : int(path.length()));
		if (path !is null && path.length() > 0)
		{
			float len = dist(from, path[0]);
			for (uint i = 1; i < path.length(); i++)
				len += dist(path[i - 1], path[i]);
			j.Num("length", len).Num("lastX", path[path.length() - 1].x).Num("lastY", path[path.length() - 1].y);
		}
		Emit(j);
	}

	// reachmap x0 y0 x1 y1 step: read-only grid of Pathfind answers from the player, one row
	// string per y ("#" a path, "." none, "@" the player's cell). Capped at REACHMAP_CAP cells.
	const int REACHMAP_CAP = 4096;

	void VerbReachmap(const string &in id, array<string>@ args)
	{
		auto plr = GetLocalPlayer();
		if (plr is null || args.length() < 5)
		{
			Fail(id, plr is null ? "no spawned local player" : "usage: reachmap x0 y0 x1 y1 step");
			return;
		}
		vec2 from = xy(plr.m_unit.GetPosition());
		float x0 = parseFloat(args[0]), y0 = parseFloat(args[1]), x1 = parseFloat(args[2]), y1 = parseFloat(args[3]);
		float st = max(16.0f, parseFloat(args[4]));
		int nx = int((x1 - x0) / st) + 1, ny = int((y1 - y0) / st) + 1;
		if (nx <= 0 || ny <= 0 || nx * ny > REACHMAP_CAP)
		{
			Fail(id, "grid " + nx + "x" + ny + " is empty or over the cap of " + REACHMAP_CAP + " cells");
			return;
		}
		array<string> rows;
		int reach = 0;
		for (int j = 0; j < ny; j++)
		{
			string row = "";
			for (int i = 0; i < nx; i++)
			{
				vec2 c(x0 + i * st, y0 + j * st);
				if (abs(c.x - from.x) <= st / 2 && abs(c.y - from.y) <= st / 2)
				{
					row += "@";
					continue;
				}
				auto path = g_scene.Pathfind(from, c, PATH_DIAMETER);
				bool ok = path !is null && path.length() > 0;
				row += ok ? "#" : ".";
				if (ok)
					reach++;
			}
			rows.insertLast(row);
		}
		Emit(Reply(id, true).Num("x0", x0).Num("y0", y0).Num("step", st).Int("nx", nx).Int("ny", ny)
			.Int("reachable", reach).Raw("rows", StrArray(rows)));
	}

	// exitareas [radius]: read-only. The nearest enabled exit's script object (its Areas: a
	// LevelExitAreaNext fires only for a player inside one), whether the player is inside each,
	// and the sensor units around the exit unit (QueryCircle getSensors), capped at SCAN_CAP.
	void VerbExitAreas(const string &in id, array<string>@ args)
	{
		auto plr = GetLocalPlayer();
		if (plr is null)
		{
			Fail(id, "no spawned local player");
			return;
		}
		vec2 pos = xy(plr.m_unit.GetPosition());
		auto ws = NearestExit(pos);
		if (ws is null)
		{
			Fail(id, "no enabled level exit");
			return;
		}
		uint radius = args.length() > 0 ? uint(parseInt(args[0])) : 600;
		vec2 at = xy(ws.GetUnit().GetPosition());
		auto j = Reply(id, true).Int("unit", ws.GetUnit().GetId()).Num("x", at.x).Num("y", at.y);
		auto ex = cast<WorldScript::LevelExitAreaNext>(ws.GetUnit().GetScriptBehavior());
		j.Bool("scriptObject", ex !is null);
		if (ex !is null && ex.Areas !is null)
		{
			array<string> areas;
			for (uint i = 0; i < ex.Areas.length(); i++)
			{
				Json a;
				a.Int("i", i).Bool("null", ex.Areas[i] is null);
				if (ex.Areas[i] !is null)
				{
					auto inside = ex.Areas[i].FetchAllInside(g_scene);
					a.Bool("playerInside", ex.Areas[i].IsInside(plr.m_unit)).Int("unitsInside", inside is null ? -1 : int(inside.length()));
					array<string> ins;
					for (uint k = 0; inside !is null && k < inside.length() && k < 8; k++)
						ins.insertLast(ScanUnit(inside[k], at));
					a.Raw("inside", RawArray(ins));
				}
				areas.insertLast(a.Close());
			}
			j.Raw("areas", RawArray(areas));
		}
		auto withS = g_scene.QueryCircle(at, radius, ~0, RaycastType::Any, true);
		auto without = g_scene.QueryCircle(at, radius, ~0, RaycastType::Any, false);
		array<string> sensors;
		uint n = 0;
		for (uint i = 0; i < withS.length(); i++)
		{
			bool plain = false;
			for (uint k = 0; k < without.length() && !plain; k++)
				plain = without[k] == withS[i];
			if (plain)
				continue;
			n++;
			if (sensors.length() < SCAN_CAP)
				sensors.insertLast(ScanUnit(withS[i], at));
		}
		j.Int("sensorCount", n).Bool("truncated", n > SCAN_CAP).Raw("sensors", RawArray(sensors));
		Emit(j);
	}

	// routesweep [spacing] [offset]: read-only. The exit route from the player (RouteExit, as the
	// exit intent plans it), then RouteExit again from points spaced along that route and
	// offset to both sides of it: where a player might be after a fight or a knock-back. Per
	// point: answered, partial, escaped, NavRoute expansions. Points a solid body covers
	// (blocked) or the player's floor does not reach (offFloor) are counted, not routed. No
	// walking: every route is planned in this one call.
	const float PLAYER_R = 8;

	void VerbRouteSweep(const string &in id, array<string>@ args)
	{
		auto plr = GetLocalPlayer();
		if (plr is null)
		{
			Fail(id, "no spawned local player");
			return;
		}
		vec2 pos = xy(plr.m_unit.GetPosition());
		auto ws = NearestExit(pos);
		if (ws is null)
		{
			Fail(id, "no enabled level exit");
			return;
		}
		float spacing = args.length() > 0 ? parseFloat(args[0]) : 400;
		float off = args.length() > 1 ? parseFloat(args[1]) : 128;
		PilotIntent it;
		@it.exitWs = ws;
		it.anchor = ExitStandPoint(ws, it.areaFound);
		bool ok = RouteExit(it, pos);
		auto j = Reply(id, true).Num("x", pos.x).Num("y", pos.y).Num("ax", it.anchor.x).Num("ay", it.anchor.y)
			.Bool("spawnOk", ok).Bool("spawnPartial", it.partial).Int("spawnExp", it.navExpanded);
		if (!ok)
		{
			Emit(j);
			return;
		}
		array<vec2> base = it.path;
		array<string> pts;
		int answered = 0, partial = 0, failed = 0, total = 0, blocked = 0, offFloor = 0;
		array<string> blockedBy;
		float acc = 0;
		for (uint i = 1; i < base.length() && total < 96; i++)
		{
			acc += dist(base[i - 1], base[i]);
			if (acc < spacing)
				continue;
			acc = 0;
			vec2 d = base[i] - base[i - 1];
			vec2 n = length(d) > 0.01f ? normalize(vec2(-d.y, d.x)) : vec2(0, 1);
			array<float> offs = { 0, off, -off };
			for (uint k = 0; k < offs.length(); k++)
			{
				vec2 q = base[i] + n * offs[k];
				PilotIntent t;
				@t.exitWs = ws;
				t.anchor = it.anchor;
				t.approach = it.approach;
				t.hasApproach = true;
				// a player can only be where no solid body overlaps its circle: the others are
				// not samples (inside a tree)
				// solid bodies other than actors (an enemy standing there does not make it a wall);
				// unit 0 hits are level collision without a unit (route-sweep 20261017-180225)
				auto hits = g_scene.QueryCircle(q, PLAYER_R, ~0, RaycastType::Any, false);
				int solid = -1;
				for (uint h = 0; h < hits.length() && solid < 0; h++)
					if (ActorOf(hits[h]) is null)
						solid = h;
				if (solid >= 0)
				{
					blocked++;
					if (blockedBy.length() < 12)
						blockedBy.insertLast(ScanUnit(hits[solid], q));
					continue;
				}
				// an off-route point the player's floor does not reach (behind the exit, across
				// a cliff: route-sweep 20261017-190749) is no sample of the planner either
				if (offs[k] != 0 && !PathOk(pos, q) && NavRoute(pos, q) is null)
				{
					offFloor++;
					continue;
				}
				bool r = RouteExit(t, q);
				total++;
				if (r && !t.partial) answered++;
				else if (r) partial++;
				else failed++;
				Json e;
				e.Num("x", q.x).Num("y", q.y).Num("off", offs[k]).Bool("walkable", Walkable(q)).Bool("ok", r)
					.Bool("partial", t.partial).Bool("escaped", t.escaped).Int("exp", t.navExpanded);
				pts.insertLast(e.Close());
			}
		}
		j.Int("points", total).Int("blocked", blocked).Int("offFloor", offFloor).Raw("blockedBy", RawArray(blockedBy)).Int("answered", answered).Int("partial", partial).Int("failed", failed).Raw("sweep", RawArray(pts));
		Emit(j);
	}

	// bodies <x> <y> [step]: read-only. Every 'step' units (default 16) from the player to x,y:
	// the collision bodies a player-sized circle overlaps (QueryCircle, sensors excluded),
	// actors flagged; Walkable (nav) and PathOk (raycast) per point. Unit ids deduplicated,
	// capped at SCAN_CAP. What stands in a passage the nav graph says is closed.
	void VerbBodies(const string &in id, array<string>@ args)
	{
		auto plr = GetLocalPlayer();
		if (plr is null || args.length() < 2)
		{
			Fail(id, plr is null ? "no spawned local player" : "usage: bodies <x> <y> [step]");
			return;
		}
		vec2 pos = xy(plr.m_unit.GetPosition());
		vec2 to(parseFloat(args[0]), parseFloat(args[1]));
		float step = args.length() > 2 ? max(4.0f, parseFloat(args[2])) : 16.0f;
		int n = int(dist(pos, to) / step) + 1;
		array<int> seen;
		array<string> bodies;
		string walk = "";
		string ray = "";
		int total = 0;
		for (int i = 0; i <= n && i <= 200; i++)
		{
			vec2 q = pos + (to - pos) * (float(i) / n);
			walk += Walkable(q) ? "1" : "0";
			ray += PathOk(pos, q) ? "1" : "0";
			auto hits = g_scene.QueryCircle(q, PLAYER_R, ~0, RaycastType::Any, false);
			for (uint h = 0; h < hits.length(); h++)
			{
				int uid = hits[h].GetId();
				if (seen.find(uid) >= 0)
					continue;
				seen.insertLast(uid);
				total++;
				if (bodies.length() < SCAN_CAP)
				{
					Json e;
					vec3 up = hits[h].GetPosition();
					e.Int("unit", uid).Str("name", hits[h].GetDebugName()).Num("x", up.x).Num("y", up.y)
						.Bool("actor", ActorOf(hits[h]) !is null).Num("atX", q.x).Num("atY", q.y);
					bodies.insertLast(e.Close());
				}
			}
		}
		auto j = Reply(id, true).Num("fx", pos.x).Num("fy", pos.y).Num("tx", to.x).Num("ty", to.y).Num("step", step)
			.Str("walkable", walk).Str("raycastFree", ray).Int("bodyCount", total).Bool("truncated", total > int(SCAN_CAP))
			.Raw("bodies", RawArray(bodies));
		Emit(j);
	}

	// breakables [radius]: read-only. Breakable units within radius (default 400) of the
	// player, nearest first: unit, name, x, y, d. Capped at SCAN_CAP, truncation reported.
	void VerbBreakables(const string &in id, array<string>@ args)
	{
		auto plr = GetLocalPlayer();
		if (plr is null)
		{
			Fail(id, "no spawned local player");
			return;
		}
		vec2 pos = xy(plr.m_unit.GetPosition());
		int radius = args.length() > 0 ? int(parseInt(args[0])) : 400;
		auto all = g_scene.FetchAllUnits(~0, pos, radius);
		array<UnitPtr> found;
		array<float> ds;
		for (uint i = 0; i < all.length(); i++)
		{
			if (!all[i].IsValid() || all[i].IsDestroyed() || cast<Breakable>(all[i].GetScriptBehavior()) is null)
				continue;
			float d = dist(pos, xy(all[i].GetPosition()));
			uint at = 0;
			while (at < ds.length() && ds[at] <= d)
				at++;
			found.insertAt(at, all[i]);
			ds.insertAt(at, d);
		}
		array<string> list;
		for (uint i = 0; i < found.length() && i < SCAN_CAP; i++)
		{
			Json e;
			vec3 up = found[i].GetPosition();
			e.Int("unit", found[i].GetId()).Str("name", found[i].GetDebugName()).Num("x", up.x).Num("y", up.y).Num("d", ds[i]);
			list.insertLast(e.Close());
		}
		Emit(Reply(id, true).Int("radius", radius).Int("count", int(found.length()))
			.Bool("truncated", found.length() > SCAN_CAP).Raw("breakables", RawArray(list)));
	}

	// exitprobe [refX refY]: read-only. Whether the nearest exit's stand point is joined to the floor the
	// player is on: Walkable(stand); per ring radius, a 16-bit string of PathOk(stand -> ring
	// point) and of PathOk(player -> ring point); NavRoute both ways (expansions, answered).
	void VerbExitProbe(const string &in id, array<string>@ args)
	{
		auto plr = GetLocalPlayer();
		if (plr is null)
		{
			Fail(id, "no spawned local player");
			return;
		}
		vec2 pos = xy(plr.m_unit.GetPosition());
		auto ws = NearestExit(pos);
		if (ws is null)
		{
			Fail(id, "no enabled level exit");
			return;
		}
		bool found;
		vec2 st = ExitStandPoint(ws, found);
		auto j = Reply(id, true).Num("px", pos.x).Num("py", pos.y).Num("sx", st.x).Num("sy", st.y)
			.Bool("area", found).Bool("walkable", Walkable(st)).Bool("direct", PathOk(pos, st));
		array<float> rings = { 64, 128, 256, 512 };
		for (uint r = 0; r < rings.length(); r++)
		{
			string fromS = "", fromP = "";
			for (int k = 0; k < 16; k++)
			{
				float ang = k * 3.14159265f / 8;
				vec2 c = st + vec2(cos(ang), sin(ang)) * rings[r];
				fromS += PathOk(st, c) ? "1" : "0";
				fromP += PathOk(pos, c) ? "1" : "0";
			}
			j.Str("s" + int(rings[r]), fromS).Str("p" + int(rings[r]), fromP);
		}
		auto fwd = NavRoute(pos, st);
		j.Bool("navFwd", fwd !is null).Int("navFwdExp", g_navExpanded);
		auto back = NavRoute(st, pos);
		j.Bool("navBack", back !is null).Int("navBackExp", g_navExpanded);
		if (args.length() >= 2)
		{
			// a reference point (the spawn): does it still route to the stand point, and here to it?
			vec2 ref(parseFloat(args[0]), parseFloat(args[1]));
			auto rs = NavRoute(ref, st);
			j.Num("rx", ref.x).Num("ry", ref.y).Bool("navRef", rs !is null).Int("navRefExp", g_navExpanded);
			auto pr = NavRoute(pos, ref);
			j.Bool("navToRef", pr !is null).Int("navToRefExp", g_navExpanded);
		}
		// every exit: enabled or not, where, and whether NavRoute reaches its stand point
		array<string> all;
		array<string> types = { "LevelExitAreaNext", "LevelExitNext" };
		for (uint t = 0; t < types.length(); t++)
		{
			auto list = g_scene.FetchAllWorldScripts(types[t]);
			for (uint i = 0; i < list.length() && all.length() < 16; i++)
			{
				bool f;
				vec2 sp = ExitStandPoint(list[i], f);
				auto r = NavRoute(pos, sp);
				Json e;
				e.Str("type", types[t]).Bool("enabled", list[i].IsEnabled())
					.Num("ux", list[i].GetUnit().GetPosition().x).Num("uy", list[i].GetUnit().GetPosition().y)
					.Num("sx", sp.x).Num("sy", sp.y).Bool("nav", r !is null).Int("exp", g_navExpanded);
				all.insertLast(e.Close());
			}
		}
		j.Raw("exits", RawArray(all));
		Emit(j);
	}

	// pfsweep <dx> <dy> <steps> [diam...]: read-only. For each diameter (default 12), whether
	// Pathfind from the player to player + k/steps * (dx,dy) answers, k = 1..steps; one bit
	// string per diameter ("1" answered). Separates "too far" from "blocked" from "too wide".
	void VerbPfSweep(const string &in id, array<string>@ args)
	{
		auto plr = GetLocalPlayer();
		if (plr is null || args.length() < 3)
		{
			Fail(id, plr is null ? "no spawned local player" : "usage: pfsweep <dx> <dy> <steps> [diam...]");
			return;
		}
		vec2 from = xy(plr.m_unit.GetPosition());
		vec2 d(parseFloat(args[0]), parseFloat(args[1]));
		int steps = max(1, min(64, int(parseInt(args[2]))));
		array<int> diams;
		for (uint i = 3; i < args.length() && diams.length() < 8; i++)
			diams.insertLast(int(parseInt(args[i])));
		if (diams.length() == 0)
			diams.insertLast(PATH_DIAMETER);
		auto reply = Reply(id, true).Num("x", from.x).Num("y", from.y).Int("steps", steps);
		for (uint j = 0; j < diams.length(); j++)
		{
			string bits = "";
			for (int k = 1; k <= steps; k++)
			{
				auto path = g_scene.Pathfind(from, from + d * (float(k) / steps), diams[j]);
				bits += (path !is null && path.length() > 0) ? "1" : "0";
			}
			reply.Str("d" + diams[j], bits);
		}
		Emit(reply);
	}

	// pfbench <n> <dx> <dy> [preN preDx preDy]: read-only. n identical Pathfind calls in one
	// frame, from the player to player + (dx,dy), after preN calls to another offset; how many
	// answered and the first that did not (a per-frame budget shows as answers stopping partway).
	void VerbPfBench(const string &in id, array<string>@ args)
	{
		auto plr = GetLocalPlayer();
		if (plr is null || args.length() < 3)
		{
			Fail(id, plr is null ? "no spawned local player" : "usage: pfbench <n> <dx> <dy> [preN preDx preDy]");
			return;
		}
		vec2 from = xy(plr.m_unit.GetPosition());
		// optional warm-up: preN calls to another target in the same frame first
		int pre = args.length() > 5 ? min(5000, int(parseInt(args[3]))) : 0;
		int preOk = 0;
		for (int i = 0; i < pre; i++)
			if (PathOk(from, from + vec2(parseFloat(args[4]), parseFloat(args[5]))))
				preOk++;
		int n = min(5000, int(parseInt(args[0])));
		vec2 to = from + vec2(parseFloat(args[1]), parseFloat(args[2]));
		int answered = 0, firstFail = -1;
		for (int i = 0; i < n; i++)
		{
			if (PathOk(from, to))
				answered++;
			else if (firstFail < 0)
				firstFail = i;
		}
		Emit(Reply(id, true).Int("n", n).Int("answered", answered).Int("firstFail", firstFail)
			.Int("pre", pre).Int("preAnswered", preOk).Num("dist", dist(from, to)));
	}

	// ---- eyes: semantic scan --------------------------------------------------

	const uint SCAN_CAP = 32;

	string ScanUnit(UnitPtr u, vec2 from)
	{
		Json e;
		vec3 p = u.GetPosition();
		e.Int("unit", u.GetId()).Str("name", u.GetDebugName()).Num("x", p.x).Num("y", p.y).Num("dist", dist(from, xy(p)));
		return e.Close();
	}

	// scan [radius]: the scene sorted into what a player acts on. Every category names the
	// field it comes from, and "raw" is the unfiltered unit list (count + first SCAN_CAP).
	void VerbScan(const string &in id, array<string>@ args)
	{
		auto plr = GetLocalPlayer();
		if (plr is null)
		{
			Fail(id, "no spawned local player");
			return;
		}
		int radius = args.length() > 0 ? int(parseInt(args[0])) : 300;
		vec2 c = xy(plr.m_unit.GetPosition());

		array<string> enemies;
		auto foes = g_scene.FetchActorsWithOtherTeam(g_team_player, c, radius);
		for (uint i = 0; i < foes.length() && enemies.length() < SCAN_CAP; i++)
		{
			auto a = ActorOf(foes[i]);
			if (a is null || a.IsDead() || !a.IsTargetable())
				continue;
			Json e;
			vec3 p = foes[i].GetPosition();
			e.Int("unit", foes[i].GetId()).Str("name", foes[i].GetDebugName()).Num("x", p.x).Num("y", p.y)
				.Num("dist", dist(c, xy(p))).Num("hp", a.GetHealth());
			enemies.insertLast(e.Close());
		}

		array<string> usables;
		array<string> raw;
		auto all = g_scene.FetchAllUnits(~0, c, radius);
		for (uint i = 0; i < all.length(); i++)
		{
			if (!all[i].IsValid() || all[i].IsDestroyed() || all[i] == plr.m_unit)
				continue;
			if (raw.length() < SCAN_CAP)
				raw.insertLast(ScanUnit(all[i], c));
			auto u = cast<IUsable>(all[i].GetScriptBehavior());
			if (u !is null && usables.length() < SCAN_CAP)
			{
				Json e;
				vec3 p = all[i].GetPosition();
				e.Int("unit", all[i].GetId()).Str("name", all[i].GetDebugName()).Str("type", Reflect::GetTypeName(u))
					.Num("x", p.x).Num("y", p.y).Num("dist", dist(c, xy(p))).Bool("canUse", u.CanUse(plr));
				usables.insertLast(e.Close());
			}
		}

		array<string> exits;
		array<string> types = { "LevelExitAreaNext", "LevelExitNext" };
		for (uint t = 0; t < types.length(); t++)
		{
			auto list = g_scene.FetchAllWorldScripts(types[t]);
			for (uint i = 0; i < list.length(); i++)
			{
				Json e;
				vec3 p = list[i].GetUnit().GetPosition();
				e.Int("unit", list[i].GetUnit().GetId()).Str("type", types[t]).Bool("enabled", list[i].IsEnabled())
					.Num("x", p.x).Num("y", p.y).Num("dist", dist(c, xy(p)));
				exits.insertLast(e.Close());
			}
		}

		Json src;
		src.Str("enemies", "Scene.FetchActorsWithOtherTeam(g_team_player): Actor.Team (Actor.as:3) != HashString(player) (Actor.as:184), alive and IsTargetable")
			.Str("usables", "unit script behavior implements IUsable (IUsable.as:33); canUse = IUsable.CanUse(player)")
			.Str("exits", "Scene.FetchAllWorldScripts(LevelExitAreaNext|LevelExitNext), whole level; enabled = WorldScript.IsEnabled")
			.Str("raw", "Scene.FetchAllUnits(~0, player, radius), first " + SCAN_CAP);
		Emit(Reply(id, true).Int("radius", radius).Num("x", c.x).Num("y", c.y).Str("level", GetCurrentLevelFilename())
			.Str("place", Place()).Int("enemyCount", enemies.length()).Int("usableCount", usables.length()).Int("exitCount", exits.length())
			.Raw("enemies", RawArray(enemies)).Raw("usables", RawArray(usables)).Raw("exits", RawArray(exits))
			.Int("rawCount", all.length()).Raw("raw", RawArray(raw)).Raw("sources", src.Close()));
	}
}

namespace Modules
{
	class GameLabPilotModule : Module
	{
		GameLabPilotModule()
		{
			super("gamelab-pilot");
			GameLab::RegisterVerb("pilot", "<intent|pause|resume|step|target|stop|status|reflex> [args] [until=..] [timeout=ms]", GameLab::Verb(GameLab::VerbPilot));
			GameLab::RegisterVerb("scan", "[radius]", GameLab::Verb(GameLab::VerbScan));
			GameLab::RegisterVerb("pathfind", "x y [diameter] [maxDistance] [maxRange] [fromX fromY]", GameLab::Verb(GameLab::VerbPathfind));
			GameLab::RegisterVerb("reachmap", "x0 y0 x1 y1 step", GameLab::Verb(GameLab::VerbReachmap));
			GameLab::RegisterVerb("exitareas", "[radius]", GameLab::Verb(GameLab::VerbExitAreas));
			GameLab::RegisterVerb("routesweep", "[spacing] [offset]", GameLab::Verb(GameLab::VerbRouteSweep));
			GameLab::RegisterVerb("bodies", "<x> <y> [step]", GameLab::Verb(GameLab::VerbBodies));
			GameLab::RegisterVerb("breakables", "[radius]", GameLab::Verb(GameLab::VerbBreakables));
			GameLab::RegisterVerb("exitprobe", "[refX refY]", GameLab::Verb(GameLab::VerbExitProbe));
			GameLab::RegisterVerb("pfsweep", "<dx> <dy> <steps> [diam...]", GameLab::Verb(GameLab::VerbPfSweep));
			GameLab::RegisterVerb("pfbench", "<n> <dx> <dy> [preN preDx preDy]", GameLab::Verb(GameLab::VerbPfBench));
		}

		void UpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused) override
		{
			// One fixed point before the ordinary paused/Pilot dispatch.
			try { GameLab::AdvanceArrivalProbe(ms, gameInput, paused); }
			catch { GameLab::g_arrivalId = ""; GameLab::g_arrivalTail = 0; }
			if (paused && GameLab::g_intent !is null && GameLab::g_intent.tight)
			{
				try { if (GameLab::TightOwnerReason(GameLab::g_intent, gameInput, "paused") != "") GameLab::g_intent.tightForeign = true; }
				catch { GameLab::g_intent.tightDiagInvalid = true; GameLab::g_intent.tightForeign = true; }
				GameLab::PilotEnd("interrupted", "tight engine paused");
			}
			if (paused)
				return;
			try {
				GameLab::PilotFrame(ms, gameInput);
			} catch {
				GameLab::g_exceptions++;
				// An ownership read may be the failing operation. Latch uncertainty
				// before End; a successful second read cannot re-authorize a tail.
				if (GameLab::g_intent !is null && GameLab::g_intent.tight)
				{
					GameLab::g_intent.tightDiagInvalid = true;
					GameLab::g_intent.tightForeign = true;
				}
				GameLab::PilotEnd("failed", "exception in the pilot frame");
			}
		}
	}
}
