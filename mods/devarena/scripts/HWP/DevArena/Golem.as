// Dev Arena: the golem room (docs/devarena/SPEC.md, Golem, Q27). One stationary target per
// floor, set to a profile (a dummy or a barracks elite) at an NG+ level and an hp pool, that
// measures every pull: damage dealt, time to kill, DPS, hits, and damage per skill.
//
// The room is built where the player stands when F4 takes them in (the floor's start until
// then, Arena.as); F4 again returns them to where they were. While the player is in it, every other enemy within
// ROOM_R is killed each frame, so the pull is the player against the golem alone. The room is
// walled with the barracks' own wall pieces (h_32 / v_32, as the barracks prefabs place them),
// produced on F4 in and destroyed on F4 out or a new floor.
//
// The golem is a normal unit (Resources::GetUnitProducer) with its own ActorProperties
// (CompositeActorProperties.LoadParams builds one per unit), edited in place:
// - m_maxHp = the pool; m_ngpScale and m_mpScaleFact = 0, so GetMaxHp
//   (CompositeActorBehavior.as:333-339) is the pool at any g_ngp.
// - armor and resistance: Damage multiplies them by 1 + g_ngp * Tweak::EnemyNGPArmorMul
//   (and ...ResistanceMul, :718-719) at hit time, so the props hold base * (1 + N*mul) /
//   (1 + g_ngp*mul) and the effective value is the profile's at NG+N whatever g_ngp is.
//   The base is what the unit loaded at the current g_ngp (its sval may pick NG+ armor).
// - passive: m_targeting false (the target is dropped, :242), m_frozen, body static, pinned.
// Damage is the drop in m_hp * GetMaxHp() each frame, so DoT counts; hits and per-skill
// damage come from the PlayerDamagedActor hook (Player.as:205), which skips DoT, so the
// difference is the breakdown's "unattributed" row. di.Weapon is the skill's m_skillId
// (PlayerBase.as:139, 240).
//
// A pull starts on the first damage and ends when the golem dies, after IDLE_MS with no
// damage, or on Abort; each ends with a `golem-pull {json}` log line.
namespace HWP
{
namespace DevArena
{
	const float ROOM_R = 300;
	const int IDLE_MS = 4000;
	const float GOLEM_OFFSET = 48;  // golem north of the room centre, player south
	const int WALL_HALF = 112;      // half the walled box's side, a multiple of 16
	const string WALL_H = "doodads/walls/barracks/h_32.unit";
	const string WALL_V = "doodads/walls/barracks/v_32.unit";
	array<UnitPtr> g_walls;

	class GolemProfile
	{
		string name;
		string unit;
		GolemProfile() {}
		GolemProfile(const string &in n, const string &in u) { name = n; unit = u; }
	}

	array<GolemProfile@> GOLEM_PROFILES = {
		GolemProfile("dummy", "doodads/generic/target_dummy_normal.unit"),
		GolemProfile("armored dummy", "doodads/generic/target_dummy_armored.unit"),
		GolemProfile("magic dummy", "doodads/generic/target_dummy_magic.unit"),
		GolemProfile("footman elite", "actors/undead/guard/guard_footman_elite.unit"),
		GolemProfile("defender elite", "actors/undead/guard/guard_defender_elite.unit"),
		GolemProfile("sentry elite", "actors/undead/guard/guard_sentry_elite.unit"),
		GolemProfile("knight", "actors/undead/guard/guard_knight.unit") };

	const array<int> GOLEM_POOLS = { 0, 1000000, 4000000, 10000000 };   // 0: the unit's own hp
	const array<string> GOLEM_DEBUFFS = { "vulnerability", "armor_break", "weakness", "marked" };
	const string DEBUFF_FILE = "tweak/buffs/status_effects.sval:";

	int g_golemProfile = 3;          // footman elite
	int g_golemPool = 1;             // 1M
	int g_golemNgp = -1;             // -1: the current g_ngp
	array<bool> g_golemDebuff = { false, false, false, false };
	int g_debuffEvery;               // 0: permanent (kept up), else re-applied every N s
	int g_debuffC;

	UnitPtr g_golem;
	vec2 g_golemAt;
	int g_golemArmor;                // effective at its NG+ (what a hit sees), for the UI
	int g_golemRes;
	bool g_inRoom;
	vec3 g_returnPos;
	int g_roomCulled;
	int g_golemSpawns;

	// pull
	bool g_pull;
	int g_pullStart;
	int g_pullLast;                  // g_clock at the last damage
	float g_pullDealt;               // from hp drops (DoT included)
	int g_pullHits;
	float g_pullHitDmg;              // from the hook (no DoT)
	// skill id -> damage (hook). Parallel arrays: a float through `dictionary` came back as
	// garbage (INT_MIN once cast) in one of two identical runs (golem-room 20261021-000549).
	array<string> g_pullSkillId;
	array<float> g_pullSkillDmg;
	float g_prevHp = -1;
	int g_pullPool;                  // the golem's max hp when the pull started
	int g_pulls;
	string g_lastPull;               // the last pull's json

	// ---- golem ------------------------------------------------------------------------
	bool IsGolem(UnitPtr u)
	{
		return g_golem.IsValid() && u.IsValid() && u == g_golem;
	}

	CompositeActorBehavior@ Golem()
	{
		if (!g_golem.IsValid())
			return null;
		auto c = cast<CompositeActorBehavior>(g_golem.GetScriptBehavior());
		return c is null || c.IsDead() ? null : c;
	}

	int GolemNgp()
	{
		return g_golemNgp >= 0 ? g_golemNgp : int(g_ngp + 0.5f);
	}

	vec2 g_roomAt;
	bool g_roomSet;

	vec2 RoomCentre()
	{
		return g_roomSet ? g_roomAt : g_arenaStart;
	}

	void KillGolem()
	{
		auto c = Golem();
		if (c !is null)
		{
			c.SetImmortal(false);
			c.Kill(null, 0);
		}
		g_golem = UnitPtr();
	}

	int Bake(int base, int n, float mul)
	{
		return int(float(base) * (1.0f + n * mul) / (1.0f + g_ngp * mul) + 0.5f);
	}

	void SpawnGolem()
	{
		EndPull("respawn");
		KillGolem();
		auto p = GOLEM_PROFILES[g_golemProfile];
		auto prod = Resources::GetUnitProducer(p.unit);
		if (prod is null)
		{
			g_lastError = "golem: no unit " + p.unit;
			return;
		}
		auto plr = LocalPlayer();
		float z = plr is null ? 0 : plr.m_unit.GetPosition().z;
		g_golemAt = RoomCentre() + vec2(0, -GOLEM_OFFSET);
		g_golem = prod.Produce(g_scene, vec3(g_golemAt.x, g_golemAt.y, z));
		auto c = cast<CompositeActorBehavior>(g_golem.GetScriptBehavior());
		if (c is null)
		{
			g_lastError = "golem: " + p.unit + " is not a CompositeActorBehavior";
			g_golem = UnitPtr();
			return;
		}
		auto pr = c.m_props;
		int n = GolemNgp();
		if (GOLEM_POOLS[g_golemPool] > 0)
			pr.m_maxHp = GOLEM_POOLS[g_golemPool];
		else
			pr.m_maxHp = c.GetMaxHp();       // the unit's own, at the current NG+
		pr.m_ngpScale = 0;
		pr.m_mpScaleFact = 0;
		pr.m_armor = Bake(pr.m_armor, n, Tweak::EnemyNGPArmorMul);
		pr.m_resistanceFire = Bake(pr.m_resistanceFire, n, Tweak::EnemyNGPResistanceMul);
		pr.m_resistanceIce = Bake(pr.m_resistanceIce, n, Tweak::EnemyNGPResistanceMul);
		pr.m_resistanceLightning = Bake(pr.m_resistanceLightning, n, Tweak::EnemyNGPResistanceMul);
		pr.m_resistancePoison = Bake(pr.m_resistancePoison, n, Tweak::EnemyNGPResistanceMul);
		pr.m_targeting = false;
		pr.m_hideHealth = false;
		g_golemArmor = int(pr.m_armor * (1.0f + g_ngp * Tweak::EnemyNGPArmorMul) + 0.5f);
		g_golemRes = int(pr.m_resistanceFire * (1.0f + g_ngp * Tweak::EnemyNGPResistanceMul) + 0.5f);
		c.m_hp = 1.0f;
		c.m_frozen = true;
		@c.m_target = null;
		g_prevHp = float(c.GetMaxHp());
		g_debuffC = 0;
		g_golemSpawns++;
		HWP::Log("devarena", "golem spawn " + p.name + " ngp " + n + " hp " + c.GetMaxHp() + " armor " + g_golemArmor
			+ " res " + g_golemRes + " at " + int(g_golemAt.x) + "," + int(g_golemAt.y));
		g_lastAction = "golem " + p.name + " NG+" + n;
	}

	// F3's part: a fresh golem (debuffs off, then the picked ones on), pull cleared
	void GolemReset()
	{
		bool had = g_golem.IsValid();
		EndPull("reset");
		g_lastPull = "";
		if (had || g_inRoom)
			SpawnGolem();
	}

	void BuildWalls(float z)
	{
		ClearWalls();
		auto h = Resources::GetUnitProducer(WALL_H);
		auto v = Resources::GetUnitProducer(WALL_V);
		if (h is null || v is null)
		{
			g_lastError = "golem: no wall units";
			return;
		}
		vec2 c = RoomCentre();
		int cx = int(c.x), cy = int(c.y);
		int l = cx - WALL_HALF, r = cx + WALL_HALF, t = cy - WALL_HALF, b = cy + WALL_HALF;
		for (int x = l; x < r; x += 32)
		{
			g_walls.insertLast(h.Produce(g_scene, vec3(x, t, z)));
			g_walls.insertLast(h.Produce(g_scene, vec3(x, b, z)));
		}
		for (int y = t; y < b; y += 32)
		{
			g_walls.insertLast(v.Produce(g_scene, vec3(l, y, z)));
			g_walls.insertLast(v.Produce(g_scene, vec3(r, y, z)));
		}
		HWP::Log("devarena", "golem walls " + g_walls.length() + " box " + l + "," + t + " " + r + "," + b);
	}

	// the player's offset from the room centre, [dx, dy]
	string PlayerFromRoom()
	{
		auto plr = LocalPlayer();
		if (plr is null)
			return "null";
		vec2 d = xy(plr.m_unit.GetPosition()) - RoomCentre();
		return "[" + int(d.x) + "," + int(d.y) + "]";
	}

	// which wall of the box the player is against (within 12 units): "e", "w", "n", "s" or ""
	string PlayerAtWall()
	{
		auto plr = LocalPlayer();
		if (plr is null || g_walls.length() == 0)
			return "";
		vec2 d = xy(plr.m_unit.GetPosition()) - RoomCentre();
		if (d.x > WALL_HALF - 12) return "e";
		if (d.x < -WALL_HALF + 12) return "w";
		if (d.y > WALL_HALF - 12) return "s";
		if (d.y < -WALL_HALF + 12) return "n";
		return "";
	}

	bool PlayerInBox()
	{
		auto plr = LocalPlayer();
		if (plr is null || g_walls.length() == 0)
			return false;
		vec2 d = xy(plr.m_unit.GetPosition()) - RoomCentre();
		return abs(d.x) < WALL_HALF && abs(d.y) < WALL_HALF;
	}

	void ClearWalls()
	{
		for (uint i = 0; i < g_walls.length(); i++)
			if (g_walls[i].IsValid())
				g_walls[i].Destroy();
		g_walls.resize(0);
	}

	void GolemNewLevel()
	{
		g_walls.resize(0);
		g_roomSet = false;
		g_golem = UnitPtr();
		g_inRoom = false;
		g_pull = false;
		g_prevHp = -1;
	}

	void GolemRoomToggle()
	{
		auto plr = LocalPlayer();
		if (plr is null)
			return;
		vec3 at = plr.m_unit.GetPosition();
		if (!g_inRoom)
		{
			g_returnPos = at;
			g_inRoom = true;
			// snapped to the 16-unit wall grid
			vec2 here = vec2(int(at.x / 16) * 16, int(at.y / 16) * 16);
			bool moved = !g_roomSet || dist(here, g_roomAt) > 0.5f;
			g_roomAt = here;
			g_roomSet = true;
			if (Golem() is null || moved)
				SpawnGolem();
			BuildWalls(at.z);
			vec2 c = RoomCentre() + vec2(0, GOLEM_OFFSET);
			plr.m_unit.SetPosition(c.x, c.y, at.z, true);
			HWP::Log("devarena", "golem room in");
			g_lastAction = "golem room (F4 back)";
		}
		else
		{
			g_inRoom = false;
			ClearWalls();
			plr.m_unit.SetPosition(g_returnPos.x, g_returnPos.y, g_returnPos.z, true);
			HWP::Log("devarena", "golem room out");
			g_lastAction = "left the golem room";
		}
	}

	void ApplyDebuffs(CompositeActorBehavior@ c)
	{
		for (uint i = 0; i < GOLEM_DEBUFFS.length(); i++)
		{
			if (!g_golemDebuff[i])
				continue;
			auto def = LoadActorBuff(DEBUFF_FILE + GOLEM_DEBUFFS[i]);
			if (def is null)
			{
				g_lastError = "no buff " + GOLEM_DEBUFFS[i];
				continue;
			}
			c.ApplyBuff(ActorBuff(null, def, 1.0f, false));
		}
	}

	void ToggleDebuff(int i)
	{
		g_golemDebuff[i] = !g_golemDebuff[i];
		HWP::Log("devarena", "golem debuff " + GOLEM_DEBUFFS[i] + " " + (g_golemDebuff[i] ? "on" : "off"));
		// off: a fresh golem drops the buff (buffs have no remove-by-def from script here)
		if (!g_golemDebuff[i] && g_golem.IsValid())
			SpawnGolem();
		g_debuffC = 0;
	}

	// ---- pull -------------------------------------------------------------------------
	string SkillName(uint hash)
	{
		if (hash == 0)
			return "(no weapon)";
		auto plr = LocalPlayer();
		if (plr !is null)
			for (uint i = 0; i < plr.m_skills.length(); i++)
				if (plr.m_skills[i].m_skillId == hash)
					return plr.m_skills[i].m_id;
		return "#" + hash;
	}

	void OnGolemHit(DamageInfo@ di)
	{
		if (!g_pull)
			StartPull();
		g_pullHits++;
		g_pullHitDmg += di.Damage;
		string k = SkillName(di.Weapon);
		int i = g_pullSkillId.find(k);
		if (i < 0)
		{
			g_pullSkillId.insertLast(k);
			g_pullSkillDmg.insertLast(0);
			i = int(g_pullSkillId.length()) - 1;
		}
		g_pullSkillDmg[i] += float(di.Damage);
		BenchOnHit();
	}

	void StartPull()
	{
		g_pull = true;
		g_pullStart = g_clock;
		g_pullLast = g_clock;
		g_pullDealt = 0;
		g_pullHits = 0;
		g_pullHitDmg = 0;
		g_pullSkillId.resize(0);
		g_pullSkillDmg.resize(0);
		auto c = Golem();
		g_pullPool = c is null ? 0 : c.GetMaxHp();
	}

	float PullSecs()
	{
		return max(0.001f, (g_pullLast - g_pullStart) / 1000.0f);
	}

	float PullDps()
	{
		return g_pull || g_pulls > 0 ? g_pullDealt / PullSecs() : 0;
	}

	// skill -> damage, largest first, with the hook-less remainder as "unattributed"
	string BreakdownJson()
	{
		array<string> rows;
		for (uint i = 0; i < g_pullSkillId.length(); i++)
			rows.insertLast("[" + GameLab::Quote(g_pullSkillId[i]) + "," + int(g_pullSkillDmg[i]) + "]");
		rows.insertLast("[\"unattributed\"," + int(max(0.0f, g_pullDealt - g_pullHitDmg)) + "]");
		return GameLab::RawArray(rows);
	}

	void EndPull(const string &in why)
	{
		if (!g_pull)
			return;
		g_pull = false;
		g_pulls++;
		auto p = GOLEM_PROFILES[g_golemProfile];
		g_lastPull = "{\"golem\":" + GameLab::Quote(p.name) + ",\"ngp\":" + GolemNgp() + ",\"pool\":" + g_pullPool
			+ ",\"end\":" + GameLab::Quote(why) + ",\"dealt\":" + int(g_pullDealt) + ",\"ms\":" + (g_pullLast - g_pullStart)
			+ ",\"ttk\":" + (why == "dead" ? g_pullLast - g_pullStart : -1) + ",\"dps\":" + int(g_pullDealt / PullSecs())
			+ ",\"hits\":" + g_pullHits + ",\"skills\":" + BreakdownJson() + ",\"preset\":" + GameLab::Quote(g_preset)
			+ ",\"version\":" + (g_onB ? g_slotB : g_slotA) + "}";
		HWP::Log("devarena", "golem-pull " + g_lastPull);
		g_lastAction = "pull " + why + ": " + int(g_pullDealt / PullSecs()) + " dps";
	}

	void TickGolem(int ms, bool paused)
	{
		if (paused)
			return;
		auto plr = LocalPlayer();
		auto c = Golem();
		if (c is null)
		{
			if (g_golem.IsValid() || g_prevHp >= 0)
			{
				// died this frame: the rest of its bar was the last of the damage
				if (g_pull && g_prevHp > 0)
				{
					g_pullDealt += g_prevHp;
					g_pullLast = g_clock;
				}
				EndPull("dead");
				g_golem = UnitPtr();
				g_prevHp = -1;
			}
		}
		else
		{
			// passive and pinned
			c.m_frozen = true;
			c.m_props.m_targeting = false;
			@c.m_target = null;
			auto body = g_golem.GetPhysicsBody();
			if (body !is null)
			{
				body.SetLinearVelocity(0, 0);
				body.SetStatic(true);
			}
			if (dist(xy(g_golem.GetPosition()), g_golemAt) > 0.01f)
				g_golem.SetPosition(g_golemAt.x, g_golemAt.y, g_golem.GetPosition().z, true);

			float hp = c.m_hp * c.GetMaxHp();
			if (g_prevHp >= 0 && hp < g_prevHp - 0.01f)
			{
				if (!g_pull)
					StartPull();
				g_pullDealt += g_prevHp - hp;
				g_pullLast = g_clock;
			}
			g_prevHp = hp;
			if (g_pull && g_clock - g_pullLast > IDLE_MS)
				EndPull("idle");

			g_debuffC -= ms;
			if (g_debuffC <= 0)
			{
				ApplyDebuffs(c);
				// statuses last 5-6 s: permanent re-applies before they run out
				g_debuffC = g_debuffEvery > 0 ? g_debuffEvery * 1000 : 4000;
			}
		}

		if (g_inRoom && plr !is null)
		{
			vec2 ctr = RoomCentre();
			auto enemies = g_scene.FetchAllActorsWithOtherTeam(g_team_player);
			for (uint i = 0; i < enemies.length(); i++)
			{
				if (IsGolem(enemies[i]) || dist(xy(enemies[i].GetPosition()), ctr) > ROOM_R)
					continue;
				auto a = cast<Actor>(enemies[i].GetScriptBehavior());
				if (a !is null && a.IsTargetable() && !a.IsDead())
				{
					a.Kill(null, 0);
					g_roomCulled++;
				}
			}
		}
	}

	// ---- layout -----------------------------------------------------------------------
	float LayoutGolem(Ui@ ui, float x, float y, float w)
	{
		float row = RowH();
		float gap = 2;
		y = Head(ui, x, y, "ROOM  (F4 in/out, F3 resets the golem)");
		float bw = (w - gap * 2) / 3;
		if (ui.Button("groom", vec4(x, y, bw, row), g_inRoom ? "Leave F4" : "Enter F4", g_inRoom ? COL_ON : COL_BUTTON))
			GolemRoomToggle();
		if (ui.Button("gspawn", vec4(x + bw + gap, y, bw, row), "Respawn"))
			SpawnGolem();
		if (ui.Button("gabort", vec4(x + (bw + gap) * 2, y, bw, row), "Abort pull", g_pull ? COL_EDIT : COL_BUTTON))
			EndPull("abort");
		y += row + PAD;

		y = Head(ui, x, y, "PROFILE");
		float hw = (w - gap) / 2;
		for (uint i = 0; i < GOLEM_PROFILES.length(); i++)
		{
			float px = x + (i % 2 == 0 ? 0 : hw + gap);
			if (ui.Button("gprof|" + GOLEM_PROFILES[i].name, vec4(px, y, hw, row), GOLEM_PROFILES[i].name,
				g_golemProfile == int(i) ? COL_ON : COL_BUTTON))
			{
				g_golemProfile = i;
				SpawnGolem();
			}
			if (i % 2 == 1 || i == GOLEM_PROFILES.length() - 1)
				y += row + 1;
		}
		y += gap;
		int n = GolemNgp();
		ui.Text(x, y + 1, "NG+", COL_DIM);
		float nx = x + w * 0.3f;
		if (ui.Button("gngp|-", vec4(nx, y, row * 1.5f, row), "-"))
		{
			g_golemNgp = max(0, n - 1);
			SpawnGolem();
		}
		ui.Text(nx + row * 1.5f + 4, y + 1, "" + n + (g_golemNgp < 0 ? " (floor)" : ""));
		if (ui.Button("gngp|+", vec4(nx + row * 5, y, row * 1.5f, row), "+"))
		{
			g_golemNgp = min(20, n + 1);
			SpawnGolem();
		}
		y += row + gap;
		ui.Text(x, y + 1, "hp", COL_DIM);
		float hx = x + w * 0.3f;
		for (uint i = 0; i < GOLEM_POOLS.length(); i++)
		{
			string l = GOLEM_POOLS[i] == 0 ? "unit" : (GOLEM_POOLS[i] / 1000000) + "M";
			float cw = ui.TextW(l) + 6;
			if (ui.Button("gpool|" + l, vec4(hx, y, cw, row), l, g_golemPool == int(i) ? COL_ON : COL_BUTTON))
			{
				g_golemPool = i;
				SpawnGolem();
			}
			hx += cw + gap;
		}
		y += row + gap;
		auto c = Golem();
		ui.Text(x, y, c is null ? "no golem (Enter or Respawn)"
			: "hp " + int(c.m_hp * c.GetMaxHp()) + "/" + c.GetMaxHp() + "  armor " + g_golemArmor + "  res " + g_golemRes, c is null ? COL_DIM : COL_TEXT);
		y += row + PAD;

		y = Head(ui, x, y, "DEBUFFS");
		float dx = x;
		for (uint i = 0; i < GOLEM_DEBUFFS.length(); i++)
		{
			string l = GOLEM_DEBUFFS[i];
			float cw = ui.TextW(l) + 6;
			if (dx + cw > x + w)
			{
				dx = x;
				y += row + 1;
			}
			if (ui.Button("gdebuff|" + l, vec4(dx, y, cw, row), l, g_golemDebuff[i] ? COL_ON : COL_BUTTON))
				ToggleDebuff(i);
			dx += cw + gap;
		}
		y += row + gap;
		ui.Text(x, y + 1, "every", COL_DIM);
		array<int> evs = { 0, 5, 10, 20 };
		float ex = x + w * 0.3f;
		for (uint i = 0; i < evs.length(); i++)
		{
			string l = evs[i] == 0 ? "kept up" : evs[i] + "s";
			float cw = ui.TextW(l) + 6;
			if (ui.Button("gevery|" + evs[i], vec4(ex, y, cw, row), l, g_debuffEvery == evs[i] ? COL_ON : COL_BUTTON))
			{
				g_debuffEvery = evs[i];
				g_debuffC = 0;
			}
			ex += cw + gap;
		}
		y += row + PAD;

		y = Head(ui, x, y, g_pull ? "PULL (live)" : "LAST PULL");
		if (!g_pull && g_pulls == 0)
		{
			ui.Text(x, y, "hit the golem to start one", COL_DIM);
			return y + row + PAD;
		}
		ui.Text(x, y, "dealt " + int(g_pullDealt) + "  " + formatFloat(PullSecs(), "", 0, 1) + "s  dps " + int(PullDps())
			+ "  hits " + g_pullHits);
		y += row;
		float top = max(1.0f, g_pullDealt);
		for (uint i = 0; i < g_pullSkillId.length(); i++)
		{
			float d = g_pullSkillDmg[i];
			ui.Fill(vec4(x, y + 1, w * min(1.0f, d / top), row - 2), COL_BAR);
			ui.Text(x + 2, y, g_pullSkillId[i] + "  " + int(d) + "  " + int(100 * d / top) + "%");
			y += row;
		}
		float un = max(0.0f, g_pullDealt - g_pullHitDmg);
		ui.Text(x + 2, y, "unattributed  " + int(un) + "  " + int(100 * un / top) + "%", COL_DIM);
		return y + row + PAD;
	}

	string GolemJson()
	{
		auto c = Golem();
		return "{\"profile\":" + GameLab::Quote(GOLEM_PROFILES[g_golemProfile].name) + ",\"ngp\":" + GolemNgp()
			+ ",\"pool\":" + GOLEM_POOLS[g_golemPool] + ",\"alive\":" + (c !is null ? "true" : "false")
			+ ",\"hp\":" + (c is null ? 0 : int(c.m_hp * c.GetMaxHp())) + ",\"maxHp\":" + (c is null ? 0 : c.GetMaxHp())
			+ ",\"armor\":" + g_golemArmor + ",\"res\":" + g_golemRes + ",\"inRoom\":" + (g_inRoom ? "true" : "false") + ",\"walls\":" + g_walls.length()
			+ ",\"culled\":" + g_roomCulled + ",\"spawns\":" + g_golemSpawns + ",\"pull\":" + (g_pull ? "true" : "false")
			+ ",\"pulls\":" + g_pulls + ",\"dealt\":" + int(g_pullDealt) + ",\"hits\":" + g_pullHits + ",\"dps\":" + int(PullDps())
			+ ",\"last\":" + (g_lastPull == "" ? "null" : g_lastPull) + "}";
	}
}
}

namespace HWPDevArenaGolem
{
	[Hook]
	void PlayerDamagedActor(Player@ p, Actor@ a, DamageInfo@ di)
	{
		// Player is the local player (remote ones are PlayerHusk)
		if (a is null || p is null)
			return;
		if (HWP::DevArena::IsGolem(a.m_unit))
			HWP::DevArena::OnGolemHit(di);
	}
}
