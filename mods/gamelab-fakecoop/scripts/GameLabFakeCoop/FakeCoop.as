// hwp fakecoop [count | off | hop <dx> <dy>]: stand-in co-op allies for looking at the party UI alone. Each is a
// real PlayerRecord in g_players (CreateCharacter, as a new character is made) with a peer id no
// one holds, and a real player_husk.unit from g_gameMode.SpawnPlayer, so HUDCoop and the party
// frames treat it as an ally. Husks don't collide, so a follower walks through walls. There is no
// peer behind them and they never fight. HP, mana, shield and potions hold at a fixed spread.
// Dev only: no network traffic is real here, and a real client's path is not exercised.
namespace GameLabFakeCoop
{
	const int MAX_ALLIES = 7;
	const string ARCANE = "hwp_sorcerer_arcane"; // starts with Living Mana (starting-level 1)
	const int REPORT_MS = 2000;   // AllyStatus forgets on level load, so keep telling it
	const float NEAR = 6;         // close enough to stand still
	const float WARP = 400;       // past this, jump: the player teleported or changed level
	const float MIN_SPEED = 90;   // pixels a second
	const float CATCH_UP = 2.5f;  // pixels a second per pixel behind

	class Ally
	{
		PlayerRecord@ record;
		float hp, mana, shield;
		int left, total;
		vec2 offset;
	}

	array<Ally@> g_allies;
	int g_reportC = 0;

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
		// a loose ring behind and beside the player
		float angle = 2.4f + 0.7f * float(g_allies.length());
		a.offset = vec2(cos(angle), sin(angle)) * (34.0f + 5.0f * float(g_allies.length()));
		g_allies.insertLast(a);
		return a;
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

	void Report()
	{
		for (uint i = 0; i < g_allies.length(); i++)
		{
			auto a = g_allies[i];
			HWP::AllyStatus::OnState(HWP::AllyStatus::Payload(a.record.peer, a.shield, a.left, a.total));
		}
	}

	void Follow(Ally@ a, Player@ me, int ms)
	{
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
			Follow(g_allies[i], me, ms);
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
			line += "; " + r.name + " " + r.playerClass.m_id + " peer " + r.peer + " dist " + d;
		}
		HWP::Log("fakecoop", line);
		HWP::Commands::Reply(line);
	}

	class GameLabFakeCoopModule : Modules::Module
	{
		GameLabFakeCoopModule()
		{
			super("gamelab-fakecoop");
			HWP::Commands::Register("fakecoop", "[count | off | hop <dx> <dy> | tutorial <id | off>]  stand-in allies that follow you (dev only)", HWP::Commands::Handler(GameLabFakeCoop::Cmd));
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
