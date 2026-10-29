// HWPTrap: HoH1's traps as one behaviour (issue #37, "add all the traps from hoh1").
//
// HoH1's traps are a few kinds of unit that its level scripts switch on and off: floor
// plates (spikes, fire, poison, drain, frost, confusion: a DangerAreaBehavior with "on" and
// "off" scenes, cycled by TimerTriggers), pressure plates (the same, set off by an area
// trigger), wall shooters (a sprite on the wall; a ShootProjectile script fires from it on
// a timer), turrets and droppers (stalactites, icicles). HoH2's generated floors have no
// level scripts to drive them, so this behaviour is the script:
//
//   off --(timer, or a player within `sense` px)--> warn --(warn ms)--> on --(on ms)--> off
//
// - "warn" is the telegraph: the unit's warn scene (HoH2's red area warning, the plate
//   lighting up) shows for `warn` ms before anything happens, so a player can step off or
//   around it (issue #38: a trap that bites with no warning feels unfair).
// - While "on", the unit's effects (DangerAreaBehavior "effects") hit every actor within
//   `radius` px every `freq` ms; with `once` they hit once, when it goes on (a dropper's
//   impact).
// - `shoot` fires projectiles when it goes on: `shots` of them over `arc` degrees around
//   `dir` (degrees, 0 = east, 90 = south), or at the nearest player with `aim`, from
//   `muzzle` px out and `muzzle-y` px down (a wall shooter's hole is above its foot); one
//   more volley every `volley-ms` while on. With `los` a "near" trap only sees players it
//   has a clear line to (a turret does not wake for a player behind a wall), and with
//   `facing` it shows its scenes for the side the shot goes to ("on_e", "off_n", ...).
// - `uses` (default endless): after that many "on"s the unit stays in its "spent" scene.
// - `setting`: a bool setting that must be on for it to go off at all (the confusion
//   glyph and plate: campaign.confusion, which says it applies now, so a trap already on
//   the floor stays dark while it is off; issue #38).
//
// Every machine runs every trap by itself, the way vanilla floor traps do: an effect only
// sticks to a player on that player's machine and to an enemy on the host
// (FilterHuskDamage), and the projectiles are local (netsync none) units, so what a player
// sees is what hits them and nothing is sent over the network. A timer trap starts at a
// point of its cycle picked from its position, so neighbouring traps do not fire in step.
class HWPTrap : DangerAreaBehavior
{
	string m_trigger;
	int m_offMs;
	int m_warnMs;
	int m_onMs;
	int m_rearmMs;
	int m_sense;
	bool m_once;
	int m_uses;

	UnitProducer@ m_shot;
	int m_shots;
	float m_arc;
	float m_dir;
	bool m_aim;
	int m_muzzle;
	int m_muzzleY;
	int m_volleyMs;
	bool m_los;
	bool m_facing;
	string m_setting;
	string m_face = "s";

	SoundEvent@ m_warnSnd;
	SoundEvent@ m_onSnd;
	SoundEvent@ m_shootSnd;
	UnitScene@ m_onFx;

	UnitScene@ m_sceneOff;
	UnitScene@ m_sceneWarn;
	UnitScene@ m_sceneOn;
	UnitScene@ m_sceneSpent;

	int m_state = 0;   // 0 off, 1 warn, 2 on, 3 spent
	int m_c;
	int m_volleyC;
	int m_fired = 0;

	HWPTrap(UnitPtr unit, SValue& params)
	{
		super(unit, params);
		m_ttl = -1;   // a trap stays (DangerAreaBehavior's default is the scene's length)
		m_unit.SetUpdateFrequency(0);

		m_trigger = GetParamString(unit, params, "trigger", false, "timer");
		m_offMs = GetParamInt(unit, params, "off", false, 2500);
		m_warnMs = GetParamInt(unit, params, "warn", false, 1000);
		m_onMs = GetParamInt(unit, params, "on", false, 1500);
		m_rearmMs = GetParamInt(unit, params, "rearm", false, 2000);
		if (m_radius <= 0)
			m_radius = 14;
		m_sense = GetParamInt(unit, params, "sense", false, m_radius + 16);
		m_once = GetParamBool(unit, params, "once", false, false);
		m_uses = GetParamInt(unit, params, "uses", false, -1);

		string shot = GetParamString(unit, params, "shoot", false);
		if (!shot.isEmpty())
			@m_shot = Resources::GetUnitProducer(shot);
		m_shots = GetParamInt(unit, params, "shots", false, 1);
		m_arc = GetParamInt(unit, params, "arc", false, 0) * PI / 180.0f;
		m_dir = GetParamInt(unit, params, "dir", false, 0) * PI / 180.0f;
		m_aim = GetParamBool(unit, params, "aim", false, false);
		m_muzzle = GetParamInt(unit, params, "muzzle", false, 8);
		m_muzzleY = GetParamInt(unit, params, "muzzle-y", false, 0);
		m_los = GetParamBool(unit, params, "los", false, false);
		m_facing = GetParamBool(unit, params, "facing", false, false);
		m_volleyMs = GetParamInt(unit, params, "volley-ms", false, 0);
		m_setting = GetParamString(unit, params, "setting", false, "");

		@m_warnSnd = Resources::GetSoundEvent(GetParamString(unit, params, "warn-snd", false));
		@m_onSnd = Resources::GetSoundEvent(GetParamString(unit, params, "on-snd", false));
		@m_shootSnd = Resources::GetSoundEvent(GetParamString(unit, params, "shoot-snd", false));
		@m_onFx = Resources::GetEffect(GetParamString(unit, params, "on-fx", false));

		if (m_facing)
			m_face = Compass(m_dir);
		LoadScenes();

		// a timer trap starts somewhere in its cycle, the same on every machine
		m_c = m_offMs;
		if (m_trigger == "timer")
		{
			vec3 p = m_unit.GetPosition();
			uint h = HashString("" + int(p.x) + "," + int(p.y));
			m_c = 1 + int(h % uint(max(1, m_offMs)));
		}
		Show(m_sceneOff);
	}

	// "e", "s", "w" or "n" for a direction in radians (screen y grows south)
	string Compass(float a)
	{
		vec2 v = vec2(cos(a), sin(a));
		if (abs(v.x) >= abs(v.y))
			return v.x >= 0 ? "e" : "w";
		return v.y >= 0 ? "s" : "n";
	}

	UnitScene@ FindScene(const string &in name)
	{
		UnitScene@ scene = null;
		if (m_facing)
			@scene = m_unit.GetUnitScene(name + "_" + m_face);
		if (scene is null)
			@scene = m_unit.GetUnitScene(name);
		return scene;
	}

	void LoadScenes()
	{
		@m_sceneOff = FindScene("off");
		@m_sceneWarn = FindScene("warn");
		@m_sceneOn = FindScene("on");
		@m_sceneSpent = FindScene("spent");
		if (m_sceneSpent is null)
			@m_sceneSpent = m_sceneOff;
	}

	void Show(UnitScene@ scene)
	{
		if (scene !is null && m_unit.GetCurrentUnitScene() !is scene)
			m_unit.SetUnitScene(scene, true);
	}

	bool PlayerNear()
	{
		vec2 here = xy(m_unit.GetPosition());
		for (uint i = 0; i < g_players.length(); i++)
		{
			auto a = g_players[i].actor;
			if (a is null || a.IsDead())
				continue;
			if (distsq(xy(a.m_unit.GetPosition()), here) > float(m_sense * m_sense))
				continue;
			if (!m_los || Sees(a.m_unit))
				return true;
		}
		return false;
	}

	// a clear line to the unit: the first thing in the way is it, or something that takes
	// hits and can be shot through (Explode's cover test); walls block
	bool Sees(UnitPtr target)
	{
		auto results = g_scene.Raycast(xy(m_unit.GetPosition()), xy(target.GetPosition()), ~0, RaycastType::Shot);
		for (uint i = 0; i < results.length(); i++)
		{
			UnitPtr u = results[i].FetchUnit(g_scene);
			if (u == m_unit)
				continue;
			if (u == target)
				return true;
			auto d = cast<IDamageTaker>(u.GetScriptBehavior());
			if (d is null || d.Impenetrable())
				return false;
		}
		return true;
	}

	Actor@ NearestPlayer()
	{
		vec2 here = xy(m_unit.GetPosition());
		Actor@ best = null;
		float bestD = 0;
		for (uint i = 0; i < g_players.length(); i++)
		{
			auto a = g_players[i].actor;
			if (a is null || a.IsDead() || (m_los && !Sees(a.m_unit)))
				continue;
			float d = distsq(xy(a.m_unit.GetPosition()), here);
			if (best is null || d < bestD)
			{
				@best = a;
				bestD = d;
			}
		}
		return best;
	}

	// where the next shot goes: at the nearest player with aim, else dir
	float ShotDir()
	{
		float dir = m_dir;
		if (m_aim)
		{
			auto target = NearestPlayer();
			if (target !is null)
			{
				// from the muzzle's height: aimed from the middle, the turret's arrows
				// (6 px up) flew past the player in parallel
				vec2 d = xy(target.m_unit.GetPosition()) - (xy(m_unit.GetPosition()) + vec2(0, m_muzzleY));
				if (lengthsq(d) > 1)
					dir = atan(d.y, d.x);
			}
		}
		return dir;
	}

	void Shoot(float dir)
	{
		if (m_shot is null)
			return;
		vec2 here = xy(m_unit.GetPosition());
		for (int i = 0; i < m_shots; i++)
		{
			float a = dir;
			if (m_shots > 1)
				a += m_arc * (float(i) / float(m_shots - 1) - 0.5f);
			vec2 v = vec2(cos(a), sin(a));
			UnitPtr proj = m_shot.Produce(g_scene, xyz(here + v * m_muzzle + vec2(0, m_muzzleY)));
			auto p = cast<IProjectile>(proj.GetScriptBehavior());
			if (p is null)
			{
				if (proj.IsValid())
					proj.Destroy();
				continue;
			}
			p.Initialize(null, ProjectileTarget(a), 1.0f, !Network::IsServer(), 0);
			m_fired++;
		}
		if (m_shootSnd !is null)
			PlaySound3D(m_shootSnd, m_unit);
	}

	void GoOn()
	{
		m_state = 2;
		m_c = m_onMs;
		m_volleyC = m_volleyMs;
		m_time = 0;   // the first tick at once
		float dir = ShotDir();
		if (m_facing)
		{
			string face = Compass(dir);
			if (face != m_face)
			{
				m_face = face;
				LoadScenes();
			}
		}
		Show(m_sceneOn);
		if (m_onSnd !is null)
			PlaySound3D(m_onSnd, m_unit);
		if (m_onFx !is null)
			PlayEffect(m_onFx, xy(m_unit.GetPosition()));
		Shoot(dir);
		if (m_once)
			TickEffects();
		if (m_uses > 0)
			m_uses--;
	}

	void Update(int dt) override
	{
		if (m_state == 3)
			return;
		m_c -= dt;
		if (m_state == 0)
		{
			bool go = m_trigger == "timer" ? m_c <= 0 : (m_c <= 0 && PlayerNear());
			if (go && m_setting != "" && !HWP::Settings::GetBool(m_setting, true))
			{
				// switched off: look again after another off spell, not every frame
				go = false;
				m_c = m_offMs;
			}
			if (go)
			{
				m_state = 1;
				m_c = m_warnMs;
				Show(m_sceneWarn !is null ? m_sceneWarn : m_sceneOff);
				if (m_warnSnd !is null)
					PlaySound3D(m_warnSnd, m_unit);
			}
		}
		else if (m_state == 1)
		{
			if (m_c <= 0)
				GoOn();
		}
		else if (m_state == 2)
		{
			if (m_volleyMs > 0)
			{
				m_volleyC -= dt;
				if (m_volleyC <= 0)
				{
					m_volleyC += m_volleyMs;
					Shoot(ShotDir());
				}
			}
			if (m_c <= 0)
			{
				if (m_uses == 0)
				{
					m_state = 3;
					Show(m_sceneSpent);
					return;
				}
				m_state = 0;
				m_c = m_trigger == "timer" ? m_offMs : m_rearmMs;
				Show(m_sceneOff);
			}
		}

		// DangerAreaBehavior's sound and tick clock; the effects only while on
		DangerAreaBehavior::Update(dt);
	}

	void TickDamage() override
	{
		if (m_state != 2 || m_once)
			return;
		TickEffects();
	}

	// every actor within the radius; the effects themselves keep to the right machine
	void TickEffects()
	{
		vec2 here = xy(m_unit.GetPosition());
		auto results = g_scene.QueryCircle(here, m_radius, ~0, RaycastType::Any, true);
		for (uint i = 0; i < results.length(); i++)
		{
			auto actor = cast<Actor>(results[i].GetScriptBehavior());
			if (actor is null || actor.IsDead())
				continue;
			if (!WorldScript::ApplyDamageFilter(results[i], m_filter))
				continue;
			ApplyDamage(results[i], xy(results[i].GetPosition()));
		}
	}

	// shots and hits for the GameLab tests
	int Fired() { return m_fired; }
	string State() { return m_state == 0 ? "off" : m_state == 1 ? "warn" : m_state == 2 ? "on" : "spent"; }
}
