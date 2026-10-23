// Dev Arena bench: A vs B on the golem, hands off (docs/devarena/SPEC.md, Bench Q28, Q17).
//
// A bench is N pulls per variant, interleaved A B A B. The variants are the tuner's A and B
// slots, or two loadouts ticked on the Loadout tab ("vs loadouts", HP3). Before each pull the
// slot is switched (the tuner's deferred apply, Tuner.as) or the loadout applied (Loadout.as
// queue), the golem respawned and cooldowns and mana reset;
// a pull lasts D seconds or until the golem dies. The driver is one of:
//   bot     the rotation: priority rules, the first whose skill is ready and whose condition
//           holds is pressed; a "main" rule is held as filler. Aims at the golem, never moves.
//   me      you play; each cast start is recorded (time, button) for replay.
//   replay  the last recording, each press at its time, queued until the skill is ready.
// bot and replay write GameInput the way gamelab-hands does (every GameInput object seen),
// and any input that is not theirs (movement, a skill or dash press) aborts the bench.
//
// RNG mode is "stats" (SPEC "Decided during build" 7): each variant is a mean with its sample
// spread, the 95% interval and the n that would pin it to +-3%; B vs A is a Welch t-test.
// tools/devarena/bench.py holds the same formulas and turns the log lines into CSV:
//   bench-pull {...} per pull, bench-result {...} per bench, bench-promote {...} on Promote.
// Procs fired = changes of a trigger's timeout or counter (Modifiers/TriggerEffect.as:149-169).
// ICD-blocked is an estimate: golem hits while a trigger's timeout is running.
namespace HWP
{
namespace DevArena
{
	const array<string> BENCH_MODES = { "bot", "me", "replay" };
	const array<string> BENCH_SOURCES = { "versions", "loadouts" };
	// the player stands this far below the golem at each pull. 74 is the room's entry spot (where
	// F4 puts you); a melee main attack does not reach from there (paladin_divine/early: 24 dps)
	const array<int> BENCH_STANDS = { 24, 48, 74 };
	const array<string> ROT_BUTTONS = { "skill1", "skill2", "skill3", "off", "main" };
	const array<string> ROT_CONDS = { "ready", "hp<", "nobuff", "stacks>=" };
	const int SETTLE_MS = 400;
	const int REPLAY_GIVEUP_MS = 2000;
	const array<float> T95 = { 12.706f, 4.303f, 3.182f, 2.776f, 2.571f, 2.447f, 2.365f, 2.306f, 2.262f, 2.228f,
		2.201f, 2.179f, 2.160f, 2.145f, 2.131f, 2.120f, 2.110f, 2.101f, 2.093f, 2.086f,
		2.080f, 2.074f, 2.069f, 2.064f, 2.060f, 2.056f, 2.052f, 2.048f, 2.045f, 2.042f };
	const string BASELINE_FILE = "tweak/hwp/devarena_baseline.sval";

	class RotRule
	{
		string button = "main";
		int cond;        // index into ROT_CONDS
		int arg = 50;    // hp% for hp<, N for stacks>=
		string buff;     // nobuff / stacks>=: a buff name or path, matched as a substring

		string Label()
		{
			string s = button;
			if (cond == 1) s += "@hp<" + arg;
			else if (cond == 2) s += "@nobuff:" + buff;
			else if (cond == 3) s += "@stacks>=" + arg + ":" + buff;
			return s;
		}
	}

	array<RotRule@> g_rules;
	int g_benchMode;                 // BENCH_MODES
	int g_benchPulls = 5;            // per variant
	int g_benchSecs = 10;
	int g_benchWhich;                // 0 A and B, 1 A only, 2 B only
	int g_benchSource;               // BENCH_SOURCES
	int g_benchStand;                // BENCH_STANDS
	string g_bWasPreset;             // loadouts: the preset applied before the bench

	// the hand recording (me), replayed by "replay"
	array<int> g_recT;
	array<string> g_recBtn;
	array<bool> g_recWas;            // per ROT_BUTTONS: casting last frame

	class BenchSide
	{
		int version = -1;
		string preset;               // loadouts: this side's preset
		array<int> dps;
		array<int> ttk;              // -1: survived the pull
		array<string> skillId;
		array<float> skillDmg;
		float unattr;
		float manaIn;
		float manaOut;
		int oomMs;
		int procs;
		int blocked;
	}

	class BStats
	{
		int n;
		float mean;
		float sd;
		float rel;
		int nFor3;
	}

	// run state
	int g_benchState;                // 0 idle, 1 switching slot, 2 settling, 3 pulling
	int g_benchId;
	array<int> g_bQueue;             // 0 A, 1 B
	int g_bIdx;
	int g_bT;                        // ms in the current phase
	bool g_bWasOnB;                  // the user's slot, put back at the end
	int g_bPullsBefore;              // g_pulls when the pull began
	BenchSide@ g_sideA;
	BenchSide@ g_sideB;
	string g_benchAbort;             // why the last bench stopped early, "" none
	string g_benchResult;            // the last bench-result json
	array<string> g_benchHistory;    // one line per bench, newest first
	string g_benchVerdict;
	string g_benchSiblings;
	int g_benchRuns;
	int g_benchAborts;
	int g_bLastSource;
	string g_bWinner;                // loadouts: the last bench's winner

	// per-pull counters
	float g_bMana = -1;
	float g_bManaIn;
	float g_bManaOut;
	int g_bOomMs;
	int g_bProcs;
	int g_bBlocked;
	array<uint> g_bTrigTimeout;
	array<int> g_bTrigCounter;
	int g_bRecK;                     // replay: next recorded press
	int g_bRecWait;                  // replay: ms the next press has been waiting
	int g_bRelease;                  // frames left before the next press (a press is one frame)
	array<bool> g_bWrote(8);         // Pressed written last frame, per hands button order
	array<int> g_bPresses(8);        // presses this pull, per hands button order
	vec2 g_bAimAt;                   // the player's position when the pull began

	// ---- rotation -----------------------------------------------------------------------
	void DefaultRotation()
	{
		g_rules.resize(0);
		array<string> order = { "skill3", "skill2", "skill1", "off", "main" };
		for (uint i = 0; i < order.length(); i++)
		{
			RotRule r;
			r.button = order[i];
			g_rules.insertLast(r);
		}
	}

	string RotationLabel()
	{
		array<string> parts;
		for (uint i = 0; i < g_rules.length(); i++)
			parts.insertLast(g_rules[i].Label());
		string s = join(parts, ">");
		return s == "skill3>skill2>skill1>off>main" ? "default" : s;
	}

	// the live skill a button fires (PlayerTargetingHelper.GetSkillInput, :713-750)
	Skills::Skill@ SkillFor(PlayerBase@ plr, const string &in button)
	{
		if (plr is null)
			return null;
		if (button == "main" || button == "off")
		{
			auto t = button == "main" ? PlayerSkillType::MainHand : PlayerSkillType::OffHand;
			for (uint i = 0; i < plr.m_skills.length(); i++)
				if (plr.m_skills[i].m_type == t)
					return plr.m_skills[i];
			return null;
		}
		int want = button == "skill1" ? 0 : button == "skill2" ? 1 : 2;
		int idx = 0;
		for (uint i = 1; i < plr.m_skills.length(); i++)
		{
			auto s = plr.m_skills[i];
			if (s.GetTargetingMode() == Skills::TargetingMode::Passive || s.m_type != PlayerSkillType::Spell)
				continue;
			if (idx == want)
				return s;
			idx++;
		}
		return null;
	}

	bool Ready(Skills::Skill@ s)
	{
		if (s is null)
			return false;
		auto a = cast<Skills::ActiveSkill>(s);
		if (a !is null && a.m_cooldownC > 0)
			return false;
		return s.CanActivate(false) && !s.IsActive();
	}

	// off cooldown but the points are not there
	bool OutOfMana(Skills::Skill@ s)
	{
		auto a = cast<Skills::ActiveSkill>(s);
		return a !is null && a.m_cooldownC <= 0 && !a.m_owner.UsePoints(false, false, a.GetCost());
	}

	bool HasBuff(ActorBuffList@ list, const string &in buff)
	{
		if (buff == "")
			return false;
		uint h = HashString(buff);
		for (uint i = 0; i < list.m_buffs.length(); i++)
		{
			auto d = list.m_buffs[i].m_def;
			if (d !is null && (d.m_pathHash == h || d.m_name.findFirst(buff) >= 0))
				return true;
		}
		return false;
	}

	int Stacks(ActorBuffList@ list, const string &in buff)
	{
		int n = 0;
		for (uint i = 0; i < list.m_stacks.length(); i++)
		{
			auto d = list.m_stacks[i].m_def;
			if (d !is null && (buff == "" || d.m_name.findFirst(buff) >= 0))
				n = max(n, list.m_stacks[i].m_stacks);
		}
		return n;
	}

	bool CondHolds(RotRule@ r, PlayerBase@ plr)
	{
		auto c = Golem();
		if (r.cond == 1)
			return c !is null && c.m_hp * 100 < r.arg;
		if (r.cond == 2)
			return !HasBuff(plr.m_buffs, r.buff);
		if (r.cond == 3)
			return c !is null && Stacks(c.m_buffs, r.buff) >= r.arg;
		return true;
	}

	// ---- input ----------------------------------------------------------------------------
	const array<string> HANDS_BUTTONS = { "use", "potion", "dash", "main", "off", "skill1", "skill2", "skill3" };
	array<GameInput@> g_benchInputs;

	// ButtonState is a value type: no handles to it
	bool PressedOf(GameInput& gi, int i)
	{
		switch (i)
		{
		case 0: return gi.Use.Pressed;
		case 1: return gi.Potion.Pressed;
		case 2: return gi.Dash.Pressed;
		case 3: return gi.MainHandAttack.Pressed;
		case 4: return gi.OffHandAttack.Pressed;
		case 5: return gi.Skill1.Pressed;
		case 6: return gi.Skill2.Pressed;
		}
		return gi.Skill3.Pressed;
	}

	void SetBtn(GameInput@ gi, int i, bool down, bool pressed)
	{
		switch (i)
		{
		case 0: gi.Use.Down = down; gi.Use.Pressed = pressed; return;
		case 1: gi.Potion.Down = down; gi.Potion.Pressed = pressed; return;
		case 2: gi.Dash.Down = down; gi.Dash.Pressed = pressed; return;
		case 3: gi.MainHandAttack.Down = down; gi.MainHandAttack.Pressed = pressed; return;
		case 4: gi.OffHandAttack.Down = down; gi.OffHandAttack.Pressed = pressed; return;
		case 5: gi.Skill1.Down = down; gi.Skill1.Pressed = pressed; return;
		case 6: gi.Skill2.Down = down; gi.Skill2.Pressed = pressed; return;
		}
		gi.Skill3.Down = down;
		gi.Skill3.Pressed = pressed;
	}

	// the engine hands out more than one GameInput (gamelab-hands Input.as:55-62): write them all
	void WriteBench(GameInput& gameInput, vec2 aim, bool aimSet, const string &in press, bool holdMain, bool mainFirst)
	{
		GameInput@ h = gameInput;
		if (g_benchInputs.findByRef(h) < 0 && g_benchInputs.length() < 8)
			g_benchInputs.insertLast(h);
		for (uint k = 0; k < g_benchInputs.length(); k++)
		{
			auto gi = g_benchInputs[k];
			gi.MoveDir = vec2(0, 0);
			if (aimSet)
				gi.AimDir = aim;
			for (int i = 0; i < 8; i++)
			{
				bool isPress = HANDS_BUTTONS[i] == press;
				bool main = i == 3 && holdMain;
				SetBtn(gi, i, isPress || main, isPress || (main && mainFirst));
				g_bWrote[i] = isPress || (main && mainFirst);
			}
		}
		if (press != "")
		{
			int k = HANDS_BUTTONS.find(press);
			if (k >= 0)
				g_bPresses[k]++;
		}
	}

	// input that is not the bench's: movement, or a press of a button it did not press
	string ForeignInput(GameInput& gi)
	{
		if (length(gi.MoveDir) > 0.2f)
			return "move";
		array<int> watch = { 0, 1, 2, 5, 6, 7 };
		for (uint i = 0; i < watch.length(); i++)
			if (PressedOf(gi, watch[i]) && !g_bWrote[watch[i]])
				return HANDS_BUTTONS[watch[i]];
		return "";
	}

	// ---- stats (tools/devarena/bench.py stats / compare) ---------------------------------
	float TCrit(int df)
	{
		if (df < 1)
			return 1e9f;
		return df <= int(T95.length()) ? T95[df - 1] : 1.96f;
	}

	BStats@ Stats(const array<int> &in v)
	{
		BStats s;
		s.n = v.length();
		if (s.n == 0)
			return s;
		float sum = 0;
		for (int i = 0; i < s.n; i++)
			sum += v[i];
		s.mean = sum / s.n;
		if (s.n > 1)
		{
			float ss = 0;
			for (int i = 0; i < s.n; i++)
				ss += (v[i] - s.mean) * (v[i] - s.mean);
			s.sd = sqrt(ss / (s.n - 1));
		}
		if (s.n < 2 || s.mean <= 0)
			return s;
		float t = TCrit(s.n - 1);
		s.rel = t * s.sd / sqrt(float(s.n)) / s.mean;
		s.nFor3 = s.sd > 0 ? int(ceil(pow(t * s.sd / (0.03f * s.mean), 2))) : s.n;
		s.nFor3 = max(s.nFor3, 2);
		return s;
	}

	string g_cmpVerdict;
	float g_cmpDelta;
	float g_cmpT;
	int g_cmpDf;

	void Compare(const array<int> &in a, const array<int> &in b)
	{
		auto sa = Stats(a);
		auto sb = Stats(b);
		g_cmpDelta = 0;
		g_cmpT = 0;
		g_cmpDf = 0;
		if (sa.n < 2 || sb.n < 2)
		{
			g_cmpVerdict = "too few pulls";
			return;
		}
		g_cmpDelta = sa.mean > 0 ? 100.0f * (sb.mean - sa.mean) / sa.mean : 0;
		float va = sa.sd * sa.sd / sa.n;
		float vb = sb.sd * sb.sd / sb.n;
		float se = sqrt(va + vb);
		if (se == 0)
		{
			g_cmpDf = sa.n + sb.n - 2;
			g_cmpVerdict = sb.mean == sa.mean ? "no difference" : (g_cmpDelta > 0 ? "B better" : "B worse");
			return;
		}
		g_cmpT = (sb.mean - sa.mean) / se;
		float den = (va > 0 ? va * va / (sa.n - 1) : 0) + (vb > 0 ? vb * vb / (sb.n - 1) : 0);
		g_cmpDf = den > 0 ? int((va + vb) * (va + vb) / den) : sa.n + sb.n - 2;
		g_cmpDf = max(1, g_cmpDf);
		if (abs(g_cmpT) < TCrit(g_cmpDf))
			g_cmpVerdict = "no difference";
		else
			g_cmpVerdict = g_cmpT > 0 ? "B better" : "B worse";
	}

	// ---- baseline (tools/devarena/bench.py baseline) ---------------------------------------
	class BaseRow
	{
		string preset;
		string golem;
		int ngp;
		int pool;
		float mean;
		float sd;
		int n;
	}
	array<BaseRow@> g_baseline;
	int g_baselineLoaded = -1;

	float FloatEntry(SValue@ d, const string &in key)
	{
		auto v = d.GetDictionaryEntry(key);
		if (v is null)
			return 0;
		if (v.GetType() == SValueType::Float)
			return v.GetFloat();
		if (v.GetType() == SValueType::Integer)
			return float(v.GetInteger());
		return 0;
	}

	void LoadBaseline()
	{
		if (g_baselineLoaded >= 0)
			return;
		g_baselineLoaded = 0;
		auto root = Resources::GetSValue(BASELINE_FILE);
		if (root is null || root.GetType() != SValueType::Dictionary)
			return;
		auto list = root.GetDictionaryEntry("rows");
		array<SValue@>@ arr = list is null ? null : list.GetArray();
		for (uint i = 0; arr !is null && i < arr.length(); i++)
		{
			BaseRow r;
			r.preset = StrEntry(arr[i], "preset");
			r.golem = StrEntry(arr[i], "golem");
			r.ngp = IntEntry(arr[i], "ngp", 0);
			r.pool = IntEntry(arr[i], "pool", 0);
			r.n = IntEntry(arr[i], "n", 0);
			r.mean = FloatEntry(arr[i], "mean");
			r.sd = FloatEntry(arr[i], "sd");
			g_baseline.insertLast(r);
		}
		g_baselineLoaded = g_baseline.length();
	}

	// "rank 2 of 3 among ranger (ranger_hunter 600, ranger_marksman 400); 9 of 24 at early"
	string SiblingVerdict(float mean, int pool)
	{
		LoadBaseline();
		if (g_preset == "")
			return "no preset applied";
		int slash = g_preset.findFirst("/");
		if (slash < 0)
			return "preset has no tier";
		string cls = g_preset.substr(0, slash);
		string tier = g_preset.substr(slash + 1);
		int us = cls.findFirst("_");
		string klass = us < 0 ? cls : cls.substr(0, us);
		string golem = GOLEM_PROFILES[g_golemProfile].name;
		int ngp = GolemNgp();
		int sibAbove = 0, sibN = 0, tierAbove = 0, tierN = 0;
		array<string> names;
		for (uint i = 0; i < g_baseline.length(); i++)
		{
			auto r = g_baseline[i];
			if (r.golem != golem || r.ngp != ngp || r.pool != pool)
				continue;
			int rs = r.preset.findFirst("/");
			if (rs < 0 || r.preset.substr(rs + 1) != tier)
				continue;
			string rc = r.preset.substr(0, rs);
			if (rc == cls)
				continue;
			tierN++;
			if (r.mean > mean)
				tierAbove++;
			int rus = rc.findFirst("_");
			if ((rus < 0 ? rc : rc.substr(0, rus)) == klass)
			{
				sibN++;
				if (r.mean > mean)
					sibAbove++;
				names.insertLast(rc + " " + int(r.mean));
			}
		}
		if (tierN == 0)
			return "no baseline for " + golem + " NG+" + ngp + " at " + tier;
		return "rank " + (sibAbove + 1) + " of " + (sibN + 1) + " among " + klass + " (" + join(names, ", ") + "); "
			+ (tierAbove + 1) + " of " + (tierN + 1) + " at " + tier;
	}

	// ---- run ------------------------------------------------------------------------------
	bool BenchRunning()
	{
		return g_benchState != 0;
	}

	void SetVariant(int v)
	{
		if (g_benchSource == 1)
		{
			string id = v == 1 ? g_sideB.preset : g_sideA.preset;
			if (g_preset != id)
				QueuePreset(id);
			return;
		}
		g_onB = v == 1;
		g_want = g_onB ? g_slotB : g_slotA;
	}

	// the variant is in place: the slot applied, or the loadout applied
	bool VariantReady()
	{
		if (Pending())
			return false;
		if (g_benchSource != 1)
			return true;
		auto side = g_bQueue[g_bIdx] == 1 ? g_sideB : g_sideA;
		return g_presetQueue.length() == 0 && g_preset == side.preset;
	}

	string SidePreset(int v)
	{
		if (g_benchSource != 1)
			return g_preset;
		return v == 1 ? g_sideB.preset : g_sideA.preset;
	}

	void RestoreVariant()
	{
		if (g_benchSource == 1)
		{
			if (g_bWasPreset != "" && g_bWasPreset != g_preset)
				QueuePreset(g_bWasPreset);
			return;
		}
		g_onB = g_bWasOnB && g_slotB >= 0;
		g_want = LiveSlotVersion();
	}

	string BenchStart()
	{
		if (BenchRunning())
			return "a bench is running";
		auto plr = LocalPlayer();
		if (plr is null)
			return "no player";
		if (g_benchMode == 2 && g_recT.length() == 0)
			return "nothing recorded: run a pull with \"me\" first";
		if (g_rules.length() == 0)
			DefaultRotation();
		if (g_benchSource == 1 && g_compare.length() != 2)
			return "tick two loadouts on the Loadout tab first";
		bool hasB = g_benchSource == 1 || g_slotB >= 0;
		bool b = hasB && g_benchWhich != 1;
		bool a = g_benchWhich != 2 || !hasB;
		if (!g_inRoom)
			GolemRoomToggle();
		g_benchId++;
		g_bQueue.resize(0);
		for (int i = 0; i < g_benchPulls; i++)
		{
			if (a) g_bQueue.insertLast(0);
			if (b) g_bQueue.insertLast(1);
		}
		@g_sideA = BenchSide();
		@g_sideB = BenchSide();
		g_sideA.version = g_benchSource == 1 ? g_want : g_slotA;
		g_sideB.version = g_benchSource == 1 ? g_want : g_slotB;
		if (g_benchSource == 1)
		{
			g_sideA.preset = g_compare[0];
			g_sideB.preset = g_compare[1];
		}
		g_bWasOnB = g_onB;
		g_bWasPreset = g_preset;
		g_bIdx = 0;
		g_benchAbort = "";
		g_benchState = 1;
		g_bT = 0;
		SetVariant(g_bQueue[0]);
		string what = g_benchSource == 1 ? "A " + g_sideA.preset + (b ? ", B " + g_sideB.preset : "")
			: "A v" + g_slotA + (b ? ", B v" + g_slotB : "");
		HWP::Log("devarena", "bench " + g_benchId + " start " + BENCH_MODES[g_benchMode] + " " + g_bQueue.length() + " pulls of "
			+ g_benchSecs + "s, " + what + ", rotation " + RotationLabel());
		g_lastAction = "bench " + g_benchId + " running";
		return "";
	}

	void BenchStop(const string &in why)
	{
		if (!BenchRunning())
			return;
		g_benchState = 0;
		g_benchAbort = why;
		g_benchAborts++;
		EndPull("abort");
		RestoreVariant();
		HWP::Log("devarena", "bench-aborted {\"bench\":" + g_benchId + ",\"why\":" + GameLab::Quote(why) + ",\"pull\":" + (g_bIdx + 1) + "}");
		g_lastAction = "bench aborted: " + why;
	}

	// what the last pull left in the room keeps hitting the next golem (reviewer: an A pull
	// after a strong B dealt 190346): player projectiles, and owned units that aren't actors
	// (areas, bolt shooters, trip mines). Summons, bombs and pets are actors and stay, as in a real fight.
	int ClearLingering(PlayerBase@ plr)
	{
		const float R = 800;
		vec2 at = RoomCentre();
		int n = 0;
		auto projs = g_scene.FetchUnitsWithBehavior("IProjectile", at, R, true);
		for (uint i = 0; i < projs.length(); i++)
		{
			auto p = cast<IProjectile>(projs[i].GetScriptBehavior());
			if (p !is null && p.Team == g_team_player)
			{
				projs[i].Destroy();
				n++;
			}
		}
		auto owned = g_scene.FetchUnitsWithBehavior("IOwnedUnit", at, R, true);
		for (uint i = 0; i < owned.length(); i++)
		{
			auto o = cast<IOwnedUnit>(owned[i].GetScriptBehavior());
			if (o is null || cast<Actor>(owned[i].GetScriptBehavior()) !is null || cast<PlayerBase>(o.GetOwner()) !is plr)
				continue;
			owned[i].Destroy();
			n++;
		}
		return n;
	}

	void ResetForPull(PlayerBase@ plr)
	{
		int cleared = ClearLingering(plr);
		if (cleared > 0)
			HWP::Log("devarena", "bench pull " + (g_bIdx + 1) + ": cleared " + cleared + " lingering units");
		SpawnGolem();
		if (g_golem.IsValid())
		{
			vec3 gp = g_golem.GetPosition();
			plr.m_unit.SetPosition(gp.x, gp.y + BENCH_STANDS[g_benchStand], gp.z, true);
		}
		for (uint i = 0; i < plr.m_skills.length(); i++)
		{
			auto a = cast<Skills::ActiveSkill>(plr.m_skills[i]);
			if (a !is null)
				a.m_cooldownC = 0;
		}
		plr.m_record.mana = 1.0f;
		g_bMana = -1;
		g_bManaIn = 0;
		g_bManaOut = 0;
		g_bOomMs = 0;
		g_bProcs = 0;
		g_bBlocked = 0;
		g_bRecK = 0;
		g_bRecWait = 0;
		g_bRelease = 0;
		g_bTargetMs = 0;
		g_bReplayMain = false;
		g_bAoe = 0;
		BenchResetTries(g_bIdx == 0);
		for (uint i = 0; i < g_bPresses.length(); i++)
			g_bPresses[i] = 0;
		g_bAimAt = xy(plr.m_unit.GetPosition());
		SnapTriggers(plr);
		if (g_benchMode == 1 && g_bIdx == 0)
		{
			// the recording is the bench's first pull (replay's times are from a pull's start)
			g_recT.resize(0);
			g_recBtn.resize(0);
			g_recWas.resize(0);
			g_recWas.resize(ROT_BUTTONS.length());
		}
	}

	void SnapTriggers(PlayerBase@ plr)
	{
		auto ts = plr.m_record.modifiers.m_triggerModifiers;
		g_bTrigTimeout.resize(ts.length());
		g_bTrigCounter.resize(ts.length());
		for (uint i = 0; i < ts.length(); i++)
		{
			g_bTrigTimeout[i] = ts[i].m_timeoutC;
			g_bTrigCounter[i] = ts[i].m_counterC;
		}
	}

	void CountTriggers(PlayerBase@ plr)
	{
		auto ts = plr.m_record.modifiers.m_triggerModifiers;
		if (ts.length() != g_bTrigTimeout.length())
		{
			SnapTriggers(plr);
			return;
		}
		for (uint i = 0; i < ts.length(); i++)
		{
			if (ts[i].m_timeoutC != g_bTrigTimeout[i] || ts[i].m_counterC != g_bTrigCounter[i])
				g_bProcs++;
			g_bTrigTimeout[i] = ts[i].m_timeoutC;
			g_bTrigCounter[i] = ts[i].m_counterC;
		}
	}

	// Golem.as OnGolemHit: a hit while a trigger's internal cooldown runs (the estimate)
	void BenchOnHit()
	{
		if (g_benchState != 3)
			return;
		auto plr = LocalPlayer();
		if (plr is null)
			return;
		auto ts = plr.m_record.modifiers.m_triggerModifiers;
		uint now = g_scene.GetTime();
		for (uint i = 0; i < ts.length(); i++)
			if (ts[i].m_timeoutC > now)
				g_bBlocked++;
	}

	void EndBenchPull(PlayerBase@ plr, bool dead)
	{
		int v = g_bQueue[g_bIdx];
		auto side = v == 1 ? g_sideB : g_sideA;
		bool hit = g_pull || g_pulls != g_bPullsBefore;
		float dealt = hit ? g_pullDealt : 0;
		int ms = max(1, g_bT);
		int dps = int(dealt * 1000 / ms);
		int ttk = dead ? ms : -1;
		float unattr = hit ? max(0.0f, g_pullDealt - g_pullHitDmg) : 0;
		array<string> rows;
		for (uint i = 0; hit && i < g_pullSkillId.length(); i++)
		{
			rows.insertLast("[" + GameLab::Quote(g_pullSkillId[i]) + "," + int(g_pullSkillDmg[i]) + "]");
			int k = side.skillId.find(g_pullSkillId[i]);
			if (k < 0)
			{
				side.skillId.insertLast(g_pullSkillId[i]);
				side.skillDmg.insertLast(0);
				k = int(side.skillId.length()) - 1;
			}
			side.skillDmg[k] += g_pullSkillDmg[i];
		}
		rows.insertLast("[\"unattributed\"," + int(unattr) + "]");
		array<string> pressed;
		for (uint i = 0; i < g_bPresses.length(); i++)
			if (g_bPresses[i] > 0)
				pressed.insertLast(GameLab::Quote(HANDS_BUTTONS[i]) + ":" + g_bPresses[i]);
		EndPull(dead ? "dead" : "bench");
		side.dps.insertLast(dps);
		side.ttk.insertLast(ttk);
		side.unattr += unattr;
		side.manaIn += g_bManaIn;
		side.manaOut += g_bManaOut;
		side.oomMs += g_bOomMs;
		side.procs += g_bProcs;
		side.blocked += g_bBlocked;
		HWP::Log("devarena", "bench-pull {\"bench\":" + g_benchId + ",\"variant\":\"" + (v == 1 ? "B" : "A") + "\",\"version\":"
			+ side.version + ",\"pull\":" + (g_bIdx + 1) + ",\"of\":" + g_bQueue.length() + ",\"preset\":" + GameLab::Quote(SidePreset(v))
			+ ",\"driver\":\"" + BENCH_MODES[g_benchMode] + "\",\"rotation\":" + GameLab::Quote(RotationLabel()) + ",\"mode\":\"stats\""
			+ ",\"golem\":" + GameLab::Quote(GOLEM_PROFILES[g_golemProfile].name) + ",\"ngp\":" + GolemNgp() + ",\"pool\":" + g_pullPoolOr()
			+ ",\"debuffs\":" + GameLab::Quote(DebuffLabel()) + ",\"dps\":" + dps + ",\"dealt\":" + int(dealt) + ",\"ms\":" + ms
			+ ",\"ttk\":" + ttk + ",\"hits\":" + (hit ? g_pullHits : 0) + ",\"manaIn\":" + int(g_bManaIn) + ",\"manaOut\":" + int(g_bManaOut)
			+ ",\"oomMs\":" + g_bOomMs + ",\"procs\":" + g_bProcs + ",\"blocked\":" + g_bBlocked + ",\"skills\":" + GameLab::RawArray(rows)
			+ ",\"presses\":{" + join(pressed, ",") + "},\"aoe\":" + g_bAoe + ",\"at\":[" + int(g_bAimAt.x) + "," + int(g_bAimAt.y) + "],\"stand\":" + BENCH_STANDS[g_benchStand]
			+ (g_benchMode == 1 ? ",\"recorded\":" + g_recT.length() : "") + "}");
	}

	int g_pullPoolOr()
	{
		return GOLEM_POOLS[g_golemPool] > 0 ? GOLEM_POOLS[g_golemPool] : g_pullPool;
	}

	string DebuffLabel()
	{
		array<string> on;
		for (uint i = 0; i < GOLEM_DEBUFFS.length(); i++)
			if (g_golemDebuff[i])
				on.insertLast(GOLEM_DEBUFFS[i]);
		return join(on, "+");
	}

	string SideJson(BenchSide@ s)
	{
		auto st = Stats(s.dps);
		int n = max(1, st.n);
		int dead = 0, ttkSum = 0;
		for (uint i = 0; i < s.ttk.length(); i++)
			if (s.ttk[i] >= 0)
			{
				dead++;
				ttkSum += s.ttk[i];
			}
		array<string> rows;
		for (uint i = 0; i < s.skillId.length(); i++)
			rows.insertLast("[" + GameLab::Quote(s.skillId[i]) + "," + int(s.skillDmg[i] / n) + "]");
		rows.insertLast("[\"unattributed\"," + int(s.unattr / n) + "]");
		return "{\"version\":" + s.version + ",\"preset\":" + GameLab::Quote(s.preset) + ",\"n\":" + st.n + ",\"mean\":" + formatFloat(st.mean, "", 0, 1) + ",\"sd\":"
			+ formatFloat(st.sd, "", 0, 1) + ",\"rel\":" + formatFloat(st.rel, "", 0, 4) + ",\"nFor3\":" + st.nFor3
			+ ",\"ttk\":" + (dead > 0 ? ttkSum / dead : -1) + ",\"kills\":" + dead + ",\"manaIn\":" + int(s.manaIn / n)
			+ ",\"manaOut\":" + int(s.manaOut / n) + ",\"oomMs\":" + s.oomMs / n + ",\"procs\":" + formatFloat(float(s.procs) / n, "", 0, 1)
			+ ",\"blocked\":" + formatFloat(float(s.blocked) / n, "", 0, 1) + ",\"skills\":" + GameLab::RawArray(rows) + "}";
	}

	void FinishBench()
	{
		g_benchState = 0;
		g_benchRuns++;
		bool hasA = g_sideA.dps.length() > 0;
		bool hasB = g_sideB.dps.length() > 0;
		if (hasA && hasB)
			Compare(g_sideA.dps, g_sideB.dps);
		else
		{
			g_cmpVerdict = "one variant";
			g_cmpDelta = 0;
		}
		auto best = Stats(hasB ? g_sideB.dps : g_sideA.dps);
		g_benchVerdict = g_cmpVerdict;
		g_bLastSource = g_benchSource;
		g_bWinner = "";
		if (g_benchSource == 1 && hasA && hasB)
		{
			// the better side; a tie ("no difference") goes to the higher mean
			bool bWins = g_cmpVerdict == "B better" || (g_cmpVerdict != "B worse" && Stats(g_sideB.dps).mean > Stats(g_sideA.dps).mean);
			g_bWinner = bWins ? g_sideB.preset : g_sideA.preset;
		}
		g_benchSiblings = SiblingVerdict(best.mean, g_pullPoolOr());
		g_benchResult = "{\"bench\":" + g_benchId + ",\"preset\":" + GameLab::Quote(SidePreset(hasB ? 1 : 0))
			+ ",\"source\":\"" + BENCH_SOURCES[g_benchSource] + "\",\"driver\":\"" + BENCH_MODES[g_benchMode]
			+ "\",\"rotation\":" + GameLab::Quote(RotationLabel()) + ",\"mode\":\"stats\",\"secs\":" + g_benchSecs
			+ ",\"golem\":" + GameLab::Quote(GOLEM_PROFILES[g_golemProfile].name) + ",\"ngp\":" + GolemNgp() + ",\"pool\":" + g_pullPoolOr()
			+ ",\"debuffs\":" + GameLab::Quote(DebuffLabel()) + ",\"nocd\":" + (g_noCd ? "true" : "false") + ",\"freeMana\":" + (g_infMana ? "true" : "false")
			+ ",\"A\":" + (hasA ? SideJson(g_sideA) : "null") + ",\"B\":" + (hasB ? SideJson(g_sideB) : "null")
			+ ",\"verdict\":" + GameLab::Quote(g_cmpVerdict) + ",\"delta\":" + formatFloat(g_cmpDelta, "", 0, 2)
			+ ",\"t\":" + formatFloat(g_cmpT, "", 0, 3) + ",\"df\":" + g_cmpDf + ",\"siblings\":" + GameLab::Quote(g_benchSiblings) + "}";
		HWP::Log("devarena", "bench-result " + g_benchResult);
		string line = "#" + g_benchId + " " + (g_preset == "" ? "-" : g_preset) + "  A " + (hasA ? "" + int(Stats(g_sideA.dps).mean) : "-")
			+ "  B " + (hasB ? "" + int(Stats(g_sideB.dps).mean) : "-") + "  " + g_cmpVerdict;
		g_benchHistory.insertAt(0, line);
		if (g_benchHistory.length() > 8)
			g_benchHistory.resize(8);
		RestoreVariant();
		g_lastAction = "bench " + g_benchId + ": " + g_cmpVerdict;
	}

	void BenchPromote()
	{
		if (g_benchResult == "")
		{
			g_lastError = "no bench result to promote";
			return;
		}
		HWP::Log("devarena", "bench-promote " + g_benchResult);
		g_lastAction = "promoted bench " + g_benchId + " (tools/devarena/bench.py promote)";
	}

	void BenchDiscardB()
	{
		if (g_slotB < 0)
		{
			g_lastError = "B is empty";
			return;
		}
		g_slotB = -1;
		g_onB = false;
		g_want = g_slotA;
		g_lastAction = "discarded B";
		HWP::Log("devarena", "bench discard B");
		EmitOverride();
	}

	// A press that leaves its skill still ready 400 ms on did not take (seen: paladin_divine/early's
	// skill2 reads CanActivate but casts nothing, 76 presses a pull). The button is skipped for 2 s,
	// so the rotation falls through to the next rule and main; logged once per bench.
	array<int> g_bTried(8);          // g_bT of the last press, per hands button order; -1 none
	array<int> g_bBackoff(8);        // skipped until this g_bT
	array<bool> g_bStuckLogged(8);

	bool BackedOff(PlayerBase@ plr, const string &in button, Skills::Skill@ s)
	{
		int k = HANDS_BUTTONS.find(button);
		if (k < 0)
			return false;
		if (g_bT < g_bBackoff[k])
			return true;
		if (g_bTried[k] >= 0 && g_bT - g_bTried[k] > 400)
		{
			g_bTried[k] = -1;
			g_bBackoff[k] = g_bT + 2000;
			if (!g_bStuckLogged[k])
			{
				g_bStuckLogged[k] = true;
				HWP::Log("devarena", "bench-stuck {\"bench\":" + g_benchId + ",\"button\":\"" + button
					+ "\",\"skill\":" + GameLab::Quote(s.m_id) + "}");
			}
			return true;
		}
		return false;
	}

	void BenchResetTries(bool bench)
	{
		for (uint i = 0; i < g_bTried.length(); i++)
		{
			g_bTried[i] = -1;
			g_bBackoff[i] = 0;
			if (bench)
				g_bStuckLogged[i] = false;
		}
	}

	// the bot's press for this frame, "" none
	string BotPress(PlayerBase@ plr, bool &out holdMain)
	{
		holdMain = false;
		for (uint i = 0; i < g_rules.length(); i++)
		{
			auto r = g_rules[i];
			auto s = SkillFor(plr, r.button);
			if (s is null)
				continue;
			if (r.button == "main")
			{
				if (CondHolds(r, plr))
				{
					holdMain = true;
					return "";
				}
				continue;
			}
			int k = HANDS_BUTTONS.find(r.button);
			if (!Ready(s))
			{
				if (k >= 0)
					g_bTried[k] = -1;
				continue;
			}
			if (BackedOff(plr, r.button, s) || !CondHolds(r, plr))
				continue;
			if (k >= 0 && g_bTried[k] < 0)
				g_bTried[k] = g_bT;
			return r.button;
		}
		return "";
	}

	string ReplayPress(PlayerBase@ plr, int ms)
	{
		while (g_bRecK < int(g_recT.length()) && g_recT[g_bRecK] <= g_bT)
		{
			if (g_recBtn[g_bRecK] == "main" || g_recBtn[g_bRecK] == "main-up")
			{
				g_bReplayMain = g_recBtn[g_bRecK] == "main";
				g_bRecK++;
				continue;
			}
			auto s = SkillFor(plr, g_recBtn[g_bRecK]);
			if (s !is null && Ready(s))
			{
				string b = g_recBtn[g_bRecK];
				g_bRecK++;
				g_bRecWait = 0;
				return b;
			}
			g_bRecWait += ms;
			if (g_bRecWait < REPLAY_GIVEUP_MS)
				return "";
			g_bRecK++;
			g_bRecWait = 0;
		}
		return "";
	}

	bool DownOf(GameInput& gi, const string &in button)
	{
		if (button == "main") return gi.MainHandAttack.Down;
		if (button == "off") return gi.OffHandAttack.Down;
		if (button == "skill1") return gi.Skill1.Down;
		if (button == "skill2") return gi.Skill2.Down;
		return gi.Skill3.Down;
	}

	// a press is a Down edge; main also records its release, so replay can hold it
	void RecordPresses(GameInput& gi)
	{
		if (g_recWas.length() != ROT_BUTTONS.length())
			g_recWas.resize(ROT_BUTTONS.length());
		for (uint i = 0; i < ROT_BUTTONS.length(); i++)
		{
			bool now = DownOf(gi, ROT_BUTTONS[i]);
			if (now != g_recWas[i] && (now || ROT_BUTTONS[i] == "main") && g_recT.length() < 2000)
			{
				g_recT.insertLast(g_bT);
				g_recBtn.insertLast(now ? ROT_BUTTONS[i] : "main-up");
			}
			g_recWas[i] = now;
		}
	}

	void TickBench(int ms, GameInput& gameInput, bool paused)
	{
		if (!BenchRunning() || paused)
			return;
		auto plr = LocalPlayer();
		if (plr is null)
		{
			BenchStop("no player");
			return;
		}
		bool drive = g_benchMode != 1;
		if (drive && g_benchState == 3 && !g_dockHover)
		{
			string f = ForeignInput(gameInput);
			if (f != "")
			{
				BenchStop("input " + f);
				gameInput.MoveDir = gameInput.MoveDir;  // leave the player's input as it is
				return;
			}
		}
		g_bT += ms;
		auto c = Golem();
		vec2 aim;
		bool aimSet = false;
		if (c !is null)
		{
			vec2 d = xy(g_golem.GetPosition()) - xy(plr.m_unit.GetPosition());
			if (length(d) > 0.01f)
			{
				aim = normalize(d);
				aimSet = true;
			}
		}

		if (g_benchState == 1)
		{
			// the tuner swaps the skills when no cast runs (Tuner.Flush)
			if (drive)
				WriteBench(gameInput, aim, false, "", false, false);
			if (VariantReady())
			{
				ResetForPull(plr);
				g_benchState = 2;
				g_bT = 0;
			}
			else if (g_bT > 10000)
				BenchStop(g_benchSource == 1 ? "the loadout never applied" : "the slot never applied");
			return;
		}
		if (g_benchState == 2)
		{
			if (drive)
				WriteBench(gameInput, aim, aimSet, "", false, false);
			if (g_bT >= SETTLE_MS)
			{
				g_benchState = 3;
				g_bT = 0;
				g_bPullsBefore = g_pulls;
				ResetCooldownsOnly(plr);
				plr.m_record.mana = 1.0f;
			}
			return;
		}

		// pulling
		float mana = plr.m_record.mana * plr.m_record.MaxMana();
		if (g_bMana >= 0)
		{
			if (mana > g_bMana)
				g_bManaIn += mana - g_bMana;
			else
				g_bManaOut += g_bMana - mana;
		}
		g_bMana = mana;
		CountTriggers(plr);
		for (uint i = 0; i < g_rules.length(); i++)
		{
			auto s = SkillFor(plr, g_rules[i].button);
			if (s !is null && OutOfMana(s))
			{
				g_bOomMs += ms;
				break;
			}
		}

		if (drive)
		{
			string press = "";
			bool holdMain = false;
			auto pl = cast<Player>(plr);
			bool targeting = pl !is null && pl.m_targetHelper !is null && pl.m_targetHelper.m_targetingSkill !is null;
			if (!targeting)
				g_bTargetMs = 0;
			if (g_bRelease > 0)
				g_bRelease--;
			else if (targeting && c !is null && ConfirmAoe(pl, aim))
				g_bRelease = 1;
			else if (targeting)
			{
				// another targeting mode (charge, aim) lands on its button's release; a main
				// press after 1 s takes the cast if it is still waiting
				g_bTargetMs += ms;
				if (g_bTargetMs > 1000)
				{
					press = "main";
					g_bRelease = 1;
					g_bTargetMs = 0;
				}
			}
			else
			{
				press = g_benchMode == 2 ? ReplayPress(plr, ms) : BotPress(plr, holdMain);
				if (g_benchMode == 2)
					holdMain = press == "" && g_bReplayMain;
				if (press != "")
					g_bRelease = 1;
			}
			bool first = holdMain && !g_bMainHeld;
			g_bMainHeld = holdMain;
			WriteBench(gameInput, aim, aimSet, press, holdMain, first);
		}
		else if (g_bIdx == 0)
			RecordPresses(gameInput);

		bool dead = c is null && g_bT > 50;
		if (dead || g_bT >= g_benchSecs * 1000)
		{
			EndBenchPull(plr, dead);
			if (drive)
				WriteBench(gameInput, aim, false, "", false, false);
			g_bMainHeld = false;
			g_bIdx++;
			if (g_bIdx >= int(g_bQueue.length()))
			{
				FinishBench();
				return;
			}
			SetVariant(g_bQueue[g_bIdx]);
			g_benchState = 1;
			g_bT = 0;
		}
	}
	bool g_bMainHeld;
	int g_bTargetMs;
	bool g_bReplayMain;

	// a TargetAOE skill waiting to be placed is placed on the golem. The player's version waits
	// for a main press at the mouse; a bot has no mouse of its own, so this is that branch,
	// with the golem's position for CalcMouseTargetPos's (Update, PlayerTargetingHelper.as:262-299)
	bool ConfirmAoe(Player@ pl, vec2 aim)
	{
		auto h = pl.m_targetHelper;
		auto s = h.m_targetingSkill;
		Skills::TargetingParams params;
		if (s.GetTargetingMode(params) != Skills::TargetingMode::TargetAOE)
			return false;
		vec2 at = h.CalcMouseTargetPos(xy(g_golem.GetPosition()), params);
		if (s.Activate(at, 1.0f))
		{
			h.CancelOther(s, aim);
			h.TriggerModifierEffects(s);
			g_bAoe++;
		}
		s.m_isActive = false;
		@h.m_targetingSkill = null;
		return true;
	}
	int g_bAoe;

	void ResetCooldownsOnly(PlayerBase@ plr)
	{
		for (uint i = 0; i < plr.m_skills.length(); i++)
		{
			auto a = cast<Skills::ActiveSkill>(plr.m_skills[i]);
			if (a !is null)
				a.m_cooldownC = 0;
		}
	}

	// ---- save -----------------------------------------------------------------------------
	string RulesString()
	{
		array<string> parts;
		for (uint i = 0; i < g_rules.length(); i++)
			parts.insertLast(g_rules[i].button + ":" + g_rules[i].cond + ":" + g_rules[i].arg + ":" + g_rules[i].buff);
		return join(parts, ";");
	}

	void RulesFromString(const string &in s)
	{
		if (s == "")
			return;
		g_rules.resize(0);
		auto parts = s.split(";");
		for (uint i = 0; i < parts.length(); i++)
		{
			auto f = parts[i].split(":");
			if (f.length() < 4 || ROT_BUTTONS.find(f[0]) < 0)
				continue;
			RotRule r;
			r.button = f[0];
			r.cond = clamp(parseInt(f[1]), 0, int(ROT_CONDS.length()) - 1);
			r.arg = parseInt(f[2]);
			r.buff = f[3];
			g_rules.insertLast(r);
		}
	}

	string RecordingString()
	{
		array<string> parts;
		for (uint i = 0; i < g_recT.length(); i++)
			parts.insertLast(g_recT[i] + ":" + g_recBtn[i]);
		return join(parts, ";");
	}

	void RecordingFromString(const string &in s)
	{
		g_recT.resize(0);
		g_recBtn.resize(0);
		if (s == "")
			return;
		auto parts = s.split(";");
		for (uint i = 0; i < parts.length(); i++)
		{
			auto f = parts[i].split(":");
			if (f.length() == 2 && (ROT_BUTTONS.find(f[1]) >= 0 || f[1] == "main-up"))
			{
				g_recT.insertLast(parseInt(f[0]));
				g_recBtn.insertLast(f[1]);
			}
		}
	}

	void SaveBench(SValueBuilder& b)
	{
		b.PushInteger("bench-mode", g_benchMode);
		b.PushInteger("bench-pulls", g_benchPulls);
		b.PushInteger("bench-secs", g_benchSecs);
		b.PushInteger("bench-which", g_benchWhich);
		b.PushInteger("bench-source", g_benchSource);
		b.PushInteger("bench-stand", g_benchStand);
		b.PushString("bench-rules", RulesString());
		b.PushString("bench-rec", RecordingString());
	}

	void LoadBench(SValue@ d)
	{
		UnitPtr u;
		g_benchMode = clamp(GetParamInt(u, d, "bench-mode", false, 0), 0, int(BENCH_MODES.length()) - 1);
		g_benchPulls = clamp(GetParamInt(u, d, "bench-pulls", false, 5), 1, 30);
		g_benchSecs = clamp(GetParamInt(u, d, "bench-secs", false, 10), 2, 60);
		g_benchWhich = clamp(GetParamInt(u, d, "bench-which", false, 0), 0, 2);
		g_benchSource = clamp(GetParamInt(u, d, "bench-source", false, 0), 0, int(BENCH_SOURCES.length()) - 1);
		g_benchStand = clamp(GetParamInt(u, d, "bench-stand", false, 0), 0, int(BENCH_STANDS.length()) - 1);
		RulesFromString(GetParamString(u, d, "bench-rules", false, ""));
		RecordingFromString(GetParamString(u, d, "bench-rec", false, ""));
	}

	void BenchNewLevel()
	{
		g_benchState = 0;
		g_benchInputs.resize(0);
	}

	// ---- layout -------------------------------------------------------------------------
	void BenchSubmit(const string &in id, const string &in text)
	{
		// "brot|<i>|buff"
		auto f = id.split("|");
		int i = f.length() >= 2 ? parseInt(f[1]) : -1;
		if (i >= 0 && i < int(g_rules.length()))
		{
			g_rules[i].buff = text.replace(":", "").replace(";", "");
			HWP::Log("devarena", "bench rule " + i + " buff '" + g_rules[i].buff + "'");
		}
	}

	float Chips(Ui@ ui, float x, float y, const string &in label, const string &in id, const array<string> &in opts, int cur, int &out pick)
	{
		float row = RowH();
		pick = -1;
		ui.Text(x, y + 1, label, COL_DIM);
		float cx = x + 44;
		for (uint i = 0; i < opts.length(); i++)
		{
			float cw = ui.TextW(opts[i]) + 6;
			if (ui.Button(id + "|" + opts[i], vec4(cx, y, cw, row), opts[i], cur == int(i) ? COL_ON : COL_BUTTON) && !BenchRunning())
				pick = i;
			cx += cw + 2;
		}
		return y + row + 2;
	}

	float LayoutBench(Ui@ ui, float x, float y, float w)
	{
		if (g_rules.length() == 0)
			DefaultRotation();
		float row = RowH();
		float gap = 2;
		int pick;

		y = Head(ui, x, y, "SETUP  (golem on the Golem tab)");
		y = Chips(ui, x, y, "driver", "bmode", BENCH_MODES, g_benchMode, pick);
		if (pick >= 0) g_benchMode = pick;
		array<string> pulls = { "3", "5", "10", "20" };
		y = Chips(ui, x, y, "pulls", "bpulls", pulls, pulls.find("" + g_benchPulls), pick);
		if (pick >= 0) g_benchPulls = parseInt(pulls[pick]);
		array<string> secs = { "5s", "10s", "20s", "30s" };
		y = Chips(ui, x, y, "secs", "bsecs", secs, secs.find(g_benchSecs + "s"), pick);
		if (pick >= 0) g_benchSecs = parseInt(secs[pick]);
		y = Chips(ui, x, y, "vs", "bsrc", BENCH_SOURCES, g_benchSource, pick);
		if (pick >= 0) g_benchSource = pick;
		array<string> stands = { "24", "48", "74" };
		y = Chips(ui, x, y, "stand", "bstand", stands, g_benchStand, pick);
		if (pick >= 0) g_benchStand = pick;
		array<string> which = { "A+B", "A", "B" };
		y = Chips(ui, x, y, "slots", "bwhich", which, g_benchWhich, pick);
		if (pick >= 0) g_benchWhich = pick;
		string ab;
		if (g_benchSource == 1)
			ab = g_compare.length() == 2 ? "A " + g_compare[0] + "   B " + g_compare[1] : "tick two loadouts (Loadout tab)";
		else
			ab = "A v" + g_slotA + (g_slotB >= 0 ? "   B v" + g_slotB : "   B empty");
		ui.Text(x, y, ab, g_benchSource == 1 && g_compare.length() != 2 ? COL_ERR : COL_DIM);
		y += row;
		ui.Text(x, y, GOLEM_PROFILES[g_golemProfile].name + " NG+" + GolemNgp() + "  pool " + (GOLEM_POOLS[g_golemPool] == 0 ? "unit" : (GOLEM_POOLS[g_golemPool] / 1000000) + "M"), COL_DIM);
		y += row + PAD;

		y = Head(ui, x, y, "ROTATION  (top first; main is held)");
		int del = -1, up = -1;
		for (uint i = 0; i < g_rules.length(); i++)
		{
			auto r = g_rules[i];
			string p = "brot|" + i + "|";
			float bx = x;
			float bw = ui.TextW("skill3") + 6;
			if (ui.Button(p + "btn", vec4(bx, y, bw, row), r.button) && !BenchRunning())
				r.button = ROT_BUTTONS[(ROT_BUTTONS.find(r.button) + 1) % ROT_BUTTONS.length()];
			bx += bw + gap;
			float cw = ui.TextW("stacks>=") + 6;
			if (ui.Button(p + "cond", vec4(bx, y, cw, row), ROT_CONDS[r.cond], r.cond == 0 ? COL_BUTTON : COL_ON) && !BenchRunning())
				r.cond = (r.cond + 1) % ROT_CONDS.length();
			bx += cw + gap;
			if (r.cond == 1 || r.cond == 3)
			{
				int step = r.cond == 1 ? 10 : 1;
				if (ui.Button(p + "-", vec4(bx, y, row, row), "-"))
					r.arg = max(r.cond == 1 ? 10 : 1, r.arg - step);
				ui.Text(bx + row + 2, y + 1, "" + r.arg);
				if (ui.Button(p + "+", vec4(bx + row * 2.6f, y, row, row), "+"))
					r.arg = min(r.cond == 1 ? 90 : 50, r.arg + step);
				bx += row * 3.6f + gap;
			}
			float right = x + w - (row + gap) * 2;
			if (r.cond >= 2)
			{
				float fw = right - bx - gap;
				if (fw > 20)
					Field(ui, p + "buff", vec4(bx, y, fw, row), r.buff == "" ? "(buff name)" : r.buff, r.buff == "" ? COL_DIM : COL_TEXT);
			}
			if (ui.Button(p + "up", vec4(right, y, row, row), "^") && i > 0)
				up = i;
			if (ui.Button(p + "x", vec4(right + row + gap, y, row, row), "x"))
				del = i;
			y += row + 1;
		}
		if (!BenchRunning())
		{
			if (up > 0)
			{
				auto t = g_rules[up - 1];
				@g_rules[up - 1] = g_rules[up];
				@g_rules[up] = t;
			}
			if (del >= 0)
				g_rules.removeAt(del);
		}
		float hw = (w - gap) / 2;
		if (ui.Button("brot-add", vec4(x, y, hw, row), "+ rule") && !BenchRunning())
		{
			RotRule r;
			r.button = "skill1";
			g_rules.insertAt(0, r);
		}
		if (ui.Button("brot-default", vec4(x + hw + gap, y, hw, row), "default") && !BenchRunning())
			DefaultRotation();
		y += row + 1;
		ui.Text(x, y, "recording: " + (g_recT.length() == 0 ? "none (driver me)" : g_recT.length() + " casts"), COL_DIM);
		y += row + PAD;

		y = Head(ui, x, y, BenchRunning() ? "RUNNING" : "RUN  (any input aborts a bot/replay bench)");
		if (!BenchRunning())
		{
			if (ui.Button("bstart", vec4(x, y, w, row), "Start bench"))
			{
				string err = BenchStart();
				if (err != "")
					g_lastError = "bench: " + err;
			}
		}
		else
		{
			if (ui.Button("babort", vec4(x, y, w * 0.3f, row), "Abort", COL_EDIT))
				BenchStop("abort button");
			string ph = g_benchState == 3 ? formatFloat(g_bT / 1000.0f, "", 0, 1) + "s" : (g_benchState == 1 ? "switching" : "reset");
			ui.Text(x + w * 0.3f + 4, y + 1, "pull " + (g_bIdx + 1) + "/" + g_bQueue.length() + "  "
				+ (g_bQueue[g_bIdx] == 1 ? "B" : "A") + "  " + ph);
		}
		y += row + 1;
		if (g_benchAbort != "")
		{
			ui.Text(x, y, "last bench stopped: " + g_benchAbort, COL_ERR);
			y += row;
		}
		y += PAD;

		y = Head(ui, x, y, "RESULT");
		bool any = g_sideA !is null && (g_sideA.dps.length() > 0 || g_sideB.dps.length() > 0);
		if (!any)
		{
			ui.Text(x, y, "no bench yet", COL_DIM);
			y += row;
		}
		else if (!BenchRunning())
		{
			vec4 vc = g_benchVerdict == "B better" ? COL_BAR : (g_benchVerdict == "B worse" ? COL_ERR : COL_TEXT);
			ui.Text(x, y, "verdict: " + g_benchVerdict + (g_cmpDelta != 0 ? "  (" + (g_cmpDelta > 0 ? "+" : "")
				+ formatFloat(g_cmpDelta, "", 0, 1) + "%)" : ""), vc);
			y += row;
			ui.Text(x, y, g_benchSiblings, COL_DIM);
			y += row;
		}
		// the verdict's buttons sit by it, above the per-skill rows (the rows run off a short dock)
		float tw = (w - gap * 3) / 4;
		if (ui.Button("bkeep", vec4(x, y, tw, row), "Keep B>A") && !BenchRunning())
			KeepB();
		if (ui.Button("bdiscard", vec4(x + tw + gap, y, tw, row), "Discard B") && !BenchRunning())
			BenchDiscardB();
		if (ui.Button("bpromote", vec4(x + (tw + gap) * 2, y, tw, row), "Promote") && !BenchRunning())
			BenchPromote();
		if (ui.Button("btuner", vec4(x + (tw + gap) * 3, y, tw, row), "To tuner", COL_BUTTON, COL_DIM))
			g_lastAction = "the auto-tuner runs outside the game (devarena-autotune); its proposal shows below";
		y += row + 1;
		y = LayoutProposal(ui, x, y + PAD, w);
		if (g_bLastSource == 1 && g_bWinner != "" && !BenchRunning())
		{
			bool fav = g_favorites.find(g_bWinner) >= 0;
			if (ui.Button("bstar", vec4(x, y, w, row), fav ? "winner " + g_bWinner + " is a favorite" : "Star winner " + g_bWinner,
				fav ? COL_ON : COL_BUTTON) && !fav)
				ToggleFavorite(g_bWinner);
			y += row + 1;
		}
		if (any)
		{
			y += PAD;
			y = SideRows(ui, x, y, w, "A", g_sideA);
			y = SideRows(ui, x, y, w, "B", g_sideB);
		}
		y += PAD;

		y = Head(ui, x, y, "HISTORY");
		if (g_benchHistory.length() == 0)
			ui.Text(x, y, "-", COL_DIM);
		for (uint i = 0; i < g_benchHistory.length(); i++)
		{
			ui.Text(x, y, g_benchHistory[i], i == 0 ? COL_TEXT : COL_DIM);
			y += row;
		}
		return y + row + PAD;
	}

	float SideRows(Ui@ ui, float x, float y, float w, const string &in name, BenchSide@ s)
	{
		float row = RowH();
		if (s.dps.length() == 0)
			return y;
		auto st = Stats(s.dps);
		int n = st.n;
		ui.Text(x, y, name + (s.preset != "" ? " " + s.preset : " v" + s.version) + "  n " + n + "  dps " + int(st.mean) + " +-" + formatFloat(100 * st.rel, "", 0, 1)
			+ "%  sd " + int(st.sd) + "  n for 3% " + st.nFor3, COL_SUB);
		y += row;
		int dead = 0, ttk = 0;
		for (uint i = 0; i < s.ttk.length(); i++)
			if (s.ttk[i] >= 0) { dead++; ttk += s.ttk[i]; }
		ui.Text(x + 6, y, "ttk " + (dead > 0 ? formatFloat(ttk / dead / 1000.0f, "", 0, 1) + "s (" + dead + " kills)" : "-")
			+ "  mana +" + int(s.manaIn / n) + " -" + int(s.manaOut / n) + "  oom " + formatFloat(s.oomMs / n / 1000.0f, "", 0, 1)
			+ "s  procs " + formatFloat(float(s.procs) / n, "", 0, 1) + "  icd~" + formatFloat(float(s.blocked) / n, "", 0, 1), COL_DIM);
		y += row;
		float total = s.unattr;
		for (uint i = 0; i < s.skillDmg.length(); i++)
			total += s.skillDmg[i];
		total = max(1.0f, total);
		for (uint i = 0; i < s.skillId.length(); i++)
		{
			float d = s.skillDmg[i];
			ui.Fill(vec4(x + 6, y + 1, (w - 6) * min(1.0f, d / total), row - 2), COL_BAR);
			ui.Text(x + 8, y, s.skillId[i] + "  " + int(d / n) + "/pull  " + int(100 * d / total) + "%");
			y += row;
		}
		ui.Text(x + 8, y, "unattributed  " + int(s.unattr / n) + "/pull  " + int(100 * s.unattr / total) + "%", COL_DIM);
		return y + row;
	}

	// da-bench: read-only. The Bench tab's settings, rotation, run state (pull, variant, phase
	// and ms in it), the last bench-result, the recording size and the baseline rows loaded.
	void VerbBench(const string &in id, array<string>@ args)
	{
		LoadBaseline();
		if (g_rules.length() == 0)
			DefaultRotation();
		array<string> rules;
		for (uint i = 0; i < g_rules.length() && i < 16; i++)
			rules.insertLast(GameLab::Quote(g_rules[i].Label()));
		string phase = g_benchState == 0 ? "idle" : g_benchState == 1 ? "switching" : g_benchState == 2 ? "settling" : "pulling";
		GameLab::Emit(GameLab::Reply(id, true).Str("driver", BENCH_MODES[g_benchMode]).Int("pulls", g_benchPulls)
			.Int("secs", g_benchSecs).Int("which", g_benchWhich).Str("rotation", RotationLabel()).Raw("rules", GameLab::RawArray(rules))
			.Bool("truncated", g_rules.length() > 16).Bool("running", BenchRunning()).Str("phase", phase).Int("bench", g_benchId)
			.Int("pull", BenchRunning() ? g_bIdx + 1 : 0).Int("queue", g_bQueue.length())
			.Str("variant", BenchRunning() ? (g_bQueue[g_bIdx] == 1 ? "B" : "A") : "").Int("ms", g_bT)
			.Str("source", BENCH_SOURCES[g_benchSource]).Str("winner", g_bWinner).Int("runs", g_benchRuns).Int("aborts", g_benchAborts).Str("aborted", g_benchAbort).Str("verdict", g_benchVerdict)
			.Int("recorded", g_recT.length()).Int("baseline", g_baseline.length()).Int("slotA", g_slotA).Int("slotB", g_slotB)
			.Bool("onB", g_onB).Int("history", g_benchHistory.length()).Raw("last", g_benchResult == "" ? "null" : g_benchResult)
			.Raw("proposal", ProposalJson()).Str("proposalLast", g_propLast).Int("proposals", g_proposals));
	}
}
}
