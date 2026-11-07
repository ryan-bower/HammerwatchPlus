// hwp fakecoop [count | off | hop <dx> <dy> | sim on/off | hit, heal, shield or kill <n | all> [percent]]:
// stand-in co-op allies for looking at the party UI alone. Each is a
// real PlayerRecord in g_players (CreateCharacter, as a new character is made) with a peer id no
// one holds, and a real player_husk.unit from g_gameMode.SpawnPlayer, so HUDCoop and the party
// frames treat it as an ally. Husks don't collide, so a follower walks through walls. There is no
// peer behind them and they never fight. HP, mana, shield and potions hold at a fixed spread
// until a command changes them, or `sim on`, which plays out a fight: hits (quicker with an enemy
// near), heals, shields, potions, deaths and respawns.
// A hit, heal or death goes through the handlers a remote player's messages reach
// (PlayerHandler::PlayerDamaged, PlayerHealed, PlayerDied), and shields and potions through
// AllyStatus::OnState. Dev only: no network traffic is real here, and enemies don't hit a husk
// (each player's own game takes their damage), so a real client's path is not exercised.
namespace GameLabFakeCoop
{
	const int MAX_ALLIES = 7;
	const string ARCANE = "hwp_sorcerer_arcane"; // starts with Living Mana (starting-level 1)
	const int REPORT_MS = 2000;   // AllyStatus forgets on level load, so keep telling it
	const float NEAR = 6;         // close enough to stand still
	const float WARP = 400;       // past this, jump: the player teleported or changed level
	const float MIN_SPEED = 90;   // pixels a second
	const float CATCH_UP = 2.5f;  // pixels a second per pixel behind
	const float ENEMY_RANGE = 110;  // an enemy this close is hitting them
	const int RESPAWN_MS = 8000;

	class Ally
	{
		PlayerRecord@ record;
		float hp, mana, shield;
		int left, total;
		vec2 offset;
		bool living;           // Living Mana: the one pool is HP and mana
		bool wired = false;    // its status comes from `wire`, not this file
		int hitC, healC, shieldC, potionC;
		int deadC = 0;
	}

	array<Ally@> g_allies;
	int g_reportC = 0;
	bool g_sim = false;

	Ally@ Add(uint8 peer, const string &in cls, const string &in name, float hp, float mana, float shield, int left, int total)
	{
		auto me = GetLocalPlayerRecord();
		auto def = PlayerClass::Get(cls);
		if (def is null && cls == ARCANE)
			@def = PlayerClass::Get("sorcerer"); // no specs mod in this run
		if (me is null || def is null)
			return null;
		PlayerRecord@ r = PlayerRecord();
		r.peer = peer;
		r.local = false;
		@r.actor = null;
		r.CreateCharacter(def, name, me.playerVoice);
		r.level = 6 + 3 * int(g_allies.length());
		g_players.insertLast(r);

		Ally a;
		@a.record = r;
		a.hp = hp;
		a.mana = mana;
		a.shield = shield;
		a.left = left;
		a.total = total;
		a.living = def is PlayerClass::Get(ARCANE);
		if (a.living)
			a.mana = hp;
		a.hitC = 1000 + randi(2000);
		a.healC = 2000 + randi(2000);
		a.shieldC = 3000 + randi(6000);
		a.potionC = 0;
		// a loose ring behind and beside the player
		float angle = 2.4f + 0.7f * float(g_allies.length());
		a.offset = vec2(cos(angle), sin(angle)) * (34.0f + 5.0f * float(g_allies.length()));
		g_allies.insertLast(a);
		return a;
	}

	void ClearCorpse(PlayerRecord@ r)
	{
		if (r.corpse is null)
			return;
		if (r.corpse.m_unit.IsValid())
			r.corpse.m_unit.Destroy();
		@r.corpse = null;
	}

	void Remove()
	{
		for (uint i = 0; i < g_allies.length(); i++)
		{
			auto r = g_allies[i].record;
			auto husk = cast<PlayerBase>(r.actor);
			if (husk !is null)
				husk.m_unit.Destroy();
			@r.actor = null;
			ClearCorpse(r);
			r.peer = 255; // as RemovePlayer leaves a record
			int index = g_players.findByRef(r);
			if (index >= 0)
				g_players.removeAt(index);
		}
		g_allies.removeRange(0, g_allies.length());
	}

	void Create(int count)
	{
		Remove();
		count = clamp(count, 0, MAX_ALLIES);
		string[] cls = { "warrior", "wizard", "priest", "rogue", ARCANE, "warlock", "paladin" };
		string[] names = { "Brakka", "Zev", "Mira", "Longnamedhero", "Sable", "Morrow", "Aldric" };
		float[] hp = { .62f, .24f, 1, .85f, .47f, .10f, .74f };
		float[] mana = { .40f, .30f, .80f, .55f, .65f, .20f, .90f };
		float[] shield = { .25f, 0, .18f, 0, .30f, 0, 1.2f };
		int[] left = { 2, 0, 3, 1, 3, 0, 2 };
		for (int i = 0; i < count; i++)
			Add(uint8(i + 1), cls[i], names[i], hp[i], mana[i], shield[i], left[i], 3);
		g_reportC = 0;
	}

	void ReportOne(Ally@ a)
	{
		if (a.wired)
			return;
		HWP::AllyStatus::OnState(HWP::AllyStatus::Payload(a.record.peer, a.shield, a.left, a.total));
	}

	void Report()
	{
		for (uint i = 0; i < g_allies.length(); i++)
			ReportOne(g_allies[i]);
	}

	void SetPool(Ally@ a, float hp)
	{
		a.hp = clamp(hp, 0.0f, 1.0f);
		if (a.living)
			a.mana = a.hp;
	}

	void Kill(Ally@ a, int damage)
	{
		a.hp = 0;
		a.shield = 0;
		a.deadC = RESPAWN_MS;
		ReportOne(a);
		PlayerHandler::PlayerDied(a.record.peer, 255, 0, damage, false, 0);
	}

	void Respawn(Ally@ a)
	{
		auto r = a.record;
		ClearCorpse(r);
		r.deadTime = 0;
		SetPool(a, .5f);
		// Follow spawns the husk next frame
	}

	// percent of max HP; a shield takes it first, as HWPSpecsShield.DamageTakenMul does
	void Hit(Ally@ a, float percent)
	{
		if (a.deadC > 0 || a.record.actor is null)
			return;
		int maxHp = a.record.MaxHealth();
		float amount = percent / 100.0f;
		float soaked = min(a.shield, amount);
		a.shield -= soaked;
		amount -= soaked;
		ReportOne(a);
		if (amount <= 0)
			return;
		int damage = max(1, int(amount * maxHp));
		if (a.hp - amount <= 0)
		{
			Kill(a, damage);
			return;
		}
		SetPool(a, a.hp - amount);
		PlayerHandler::PlayerDamaged(a.record.peer, 0, damage, a.hp, 0);
	}

	void Heal(Ally@ a, float percent)
	{
		if (a.deadC > 0 || a.record.actor is null)
			return;
		float next = min(1.0f, a.hp + percent / 100.0f);
		int amount = max(1, int((next - a.hp) * a.record.MaxHealth()));
		SetPool(a, next);
		PlayerHandler::PlayerHealed(a.record.peer, amount, a.hp);
	}

	void Shield(Ally@ a, float percent)
	{
		a.shield = max(a.shield, percent / 100.0f);
		ReportOne(a);
	}

	bool EnemyNear(Ally@ a)
	{
		auto husk = cast<PlayerHusk>(a.record.actor);
		if (husk is null)
			return false;
		return g_scene.FetchActorsWithOtherTeam(husk.Team, xy(husk.m_unit.GetPosition()), uint(ENEMY_RANGE)).length() > 0;
	}

	// a fight seen from the party UI: nothing here is drawn from a real one
	void Simulate(Ally@ a, int ms)
	{
		if (a.deadC > 0)
		{
			a.deadC -= ms;
			if (a.deadC <= 0)
				Respawn(a);
			return;
		}
		if (a.record.actor is null)
			return;
		if (a.living)
			SetPool(a, a.hp + 0.00003f * ms);
		else
			a.mana = min(1.0f, a.mana + 0.00002f * ms);

		a.hitC -= ms;
		if (a.hitC <= 0)
		{
			bool near = EnemyNear(a);
			a.hitC = near ? 500 + randi(500) : 1800 + randi(2200);
			Hit(a, 6.0f + randf() * 12.0f);
			if (!a.living)
				a.mana = max(0.0f, a.mana - 0.03f - randf() * 0.05f);
		}
		a.healC -= ms;
		if (a.healC <= 0)
		{
			a.healC = 2200 + randi(2000);
			if (a.hp < .6f)
				Heal(a, 5 + randi(8));
		}
		a.shieldC -= ms;
		if (a.shieldC <= 0)
		{
			a.shieldC = 10000 + randi(9000);
			Shield(a, randi(6) == 0 ? 120 : 15 + randi(26)); // now and then past the bar's end
		}
		a.potionC -= ms;
		if (a.potionC <= 0)
		{
			a.potionC = 6000;
			if (a.hp < .3f && a.left > 0)
			{
				a.left--;
				ReportOne(a);
				Heal(a, 35);
			}
			else if (a.left < a.total && randi(4) == 0)
			{
				a.left++; // a well or a refill: a report is all that carries it
				ReportOne(a);
			}
		}
	}

	// hit, heal, shield or kill <n | all> [percent]; n counts from 1
	void Act(array<string>@ args)
	{
		float percent = args.length() > 2 ? parseFloat(args[2]) : 25.0f;
		bool all = args.length() < 2 || args[1] == "all";
		for (uint i = 0; i < g_allies.length(); i++)
		{
			if (!all && int(i) + 1 != parseInt(args[1]))
				continue;
			auto a = g_allies[i];
			if (args[0] == "hit")
				Hit(a, percent);
			else if (args[0] == "heal")
				Heal(a, percent);
			else if (args[0] == "shield")
				Shield(a, percent);
			else if (a.deadC <= 0 && a.record.actor !is null)
				Kill(a, a.record.MaxHealth());
		}
	}

	void Follow(Ally@ a, Player@ me, int ms)
	{
		if (a.deadC > 0)
			return;
		auto r = a.record;
		r.hp = a.hp;
		r.mana = a.mana;
		vec2 target = xy(me.m_unit.GetPosition()) + a.offset;
		if (r.actor is null)
		{
			g_gameMode.SpawnPlayer(g_players.findByRef(r), target);
			return;
		}
		auto husk = cast<PlayerHusk>(r.actor);
		if (husk is null || husk.m_unit.IsDestroyed())
			return;
		vec2 pos = xy(husk.m_unit.GetPosition());
		vec2 delta = target - pos;
		float d = length(delta);
		if (d >= WARP)
			husk.MovePlayer(target, husk.m_dir);
		else if (d > NEAR)
		{
			float step = min(d, max(MIN_SPEED, d * CATCH_UP) * float(ms) / 1000.0f);
			husk.MovePlayer(pos + delta * (step / d), delta * (1.0f / d));
		}
	}

	void Update(int ms)
	{
		if (g_allies.length() == 0)
			return;
		auto me = GetLocalPlayer();
		if (me is null)
			return;
		for (uint i = 0; i < g_allies.length(); i++)
		{
			if (g_sim || g_allies[i].deadC > 0)
				Simulate(g_allies[i], ms);
			Follow(g_allies[i], me, ms);
		}
		g_reportC -= ms;
		if (g_reportC <= 0)
		{
			g_reportC = REPORT_MS;
			Report();
		}
	}

	// hwp fakecoop listend: the open Plus tab's list, scrolled as far as it goes. Prints how far
	// the last visible row's bottom sits past the list's bottom: above 0, it can't be reached
	void ListEnd()
	{
		auto gm = cast<HWR2GameMode>(g_gameMode);
		for (uint i = 0; gm !is null && i < gm.m_windowManager.m_objects.length(); i++)
		{
			auto menu = cast<PlayerMenu>(gm.m_windowManager.m_objects[i]);
			if (menu is null)
				continue;
			auto tab = cast<HWPOptionsTab>(menu.m_tabSystem.m_tabs[menu.m_tabSystem.m_currentIndex]);
			if (tab is null || tab.m_list is null)
				continue;
			auto list = tab.m_list;
			list.m_handleValue = 1;
			list.DoLayout(list.m_origin - list.m_offset, vec2(list.m_width, list.m_height));
			int bottom = -100000, rows = 0;
			for (uint r = 0; r < tab.m_rows.length(); r++)
			{
				auto w = tab.m_rows[r].w;
				if (!w.m_visible)
					continue;
				rows++;
				bottom = max(bottom, int(w.m_origin.y) + w.m_height);
			}
			int over = bottom - int(list.m_origin.y) - list.m_height;
			HWP::Log("fakecoop", "listend: rows " + rows + ", children height " + list.m_childrenHeight + ", list " + list.m_height + ", past the bottom " + over);
			return;
		}
		HWP::Log("fakecoop", "listend: no Plus tab open");
	}

	// hwp fakecoop tutorial <id | off>: the game's own panel, as a level's TutorialArea raises it
	void ForceTutorial(const string &in id)
	{
		auto gm = cast<AGameplayGameMode>(g_gameMode);
		for (uint i = 0; gm !is null && i < gm.m_modules.length(); i++)
		{
			auto mod = cast<Tutorials::TutorialModule>(gm.m_modules[i]);
			if (mod is null)
				continue;
			auto tut = Tutorials::Tutorial::Get(id);
			if (tut !is null)
				tut.m_shown = false;
			mod.ShowTutorial(tut);
			HWP::Log("fakecoop", "tutorial " + id + (tut is null ? ": none" : ": showing"));
			return;
		}
		HWP::Log("fakecoop", "tutorial: no module here");
	}

	// what a client's report does on the host, with values another game really sent: the harness
	// carries them, so this is the host's handler and the frames, not Steam or the engine's transport
	void Wire(array<string>@ args)
	{
		int n = parseInt(args[1]);
		if (n < 1 || n > int(g_allies.length()))
			return;
		auto a = g_allies[n - 1];
		a.wired = true;
		auto data = HWP::AllyStatus::Payload(-1, parseFloat(args[2]), parseInt(args[3]), parseInt(args[4]));
		HWP::AllyStatus::OnReport(a.record.peer, data);
		data.Delete();
	}

	void Cmd(array<string>@ args)
	{
		if (args.length() > 0)
		{
			if (args[0] == "off")
				Remove();
			else if (args[0] == "listend")
				ListEnd();
			else if (args[0] == "tutorial" && args.length() > 1)
				ForceTutorial(args[1]);
			else if (args[0] == "wire" && args.length() > 4)
				Wire(args);
			else if (args[0] == "sim")
				g_sim = args.length() < 2 || args[1] != "off";
			else if (args[0] == "hit" || args[0] == "heal" || args[0] == "shield" || args[0] == "kill")
				Act(args);
			else if (args[0] == "hop" && args.length() > 2 && GetLocalPlayer() !is null)
			{
				// the scenario's way to make the player move: it can't know where the floor put them
				auto u = GetLocalPlayer().m_unit;
				vec2 at = xy(u.GetPosition()) + vec2(parseFloat(args[1]), parseFloat(args[2]));
				u.SetPosition(at.x, at.y, 0, true);
			}
			else
				Create(parseInt(args[0]));
		}
		auto me = GetLocalPlayer();
		string line = "fakecoop: " + g_allies.length() + " allies";
		for (uint i = 0; i < g_allies.length() && me !is null; i++)
		{
			auto r = g_allies[i].record;
			auto husk = cast<PlayerHusk>(r.actor);
			int d = husk is null ? -1 : int(length(xy(husk.m_unit.GetPosition()) - xy(me.m_unit.GetPosition())) + 0.5f);
			line += "; " + r.name + " " + r.playerClass.m_id + " peer " + r.peer + " dist " + d
				+ " hp " + int(floor(r.hp * 100 + 0.5f)) + " shield " + int(floor(g_allies[i].shield * 100 + 0.5f)) + (r.IsDead() ? " dead" : "");
		}
		HWP::Log("fakecoop", line);
		HWP::Commands::Reply(line);
	}

	class GameLabFakeCoopModule : Modules::Module
	{
		GameLabFakeCoopModule()
		{
			super("gamelab-fakecoop");
			HWP::Commands::Register("fakecoop", "[count | off | hop <dx> <dy> | tutorial <id | off> | sim on/off | hit, heal, shield or kill <n | all> [percent] | wire <n> <shield> <left> <total>]  stand-in allies that follow you (dev only)", HWP::Commands::Handler(GameLabFakeCoop::Cmd));
		}

		HWP::Guard m_guardUpdateFrame;
		void UpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused) override
		{
			if (m_guardUpdateFrame.Skip("gamelab-fakecoop", "GameLabFakeCoopModule.UpdateFrame"))
				return;
			if (m_guardUpdateFrame.Raw())
			{
				if (!paused)
					GameLabFakeCoop::Update(ms);
				m_guardUpdateFrame.Ok();
				return;
			}
			try
			{
				if (!paused)
					GameLabFakeCoop::Update(ms);
				m_guardUpdateFrame.Ok();
			}
			catch { m_guardUpdateFrame.Failed(); }
		}
	}
}
